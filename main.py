import os
import logging
import requests
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
from gtts import gTTS
import telegram
from telegram import Bot

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('news_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

NEWS_API_URL = "https://newsapi.org/v2/everything"


def fetch_news_by_category(categories: List[str] = ['technology', 'business', 'general'], 
                           articles_per_category: int = 10) -> Dict[str, List[Dict]]:
    """
    Fetch latest news from NewsAPI for India by categories.
    
    Args:
        categories: List of categories to fetch
        articles_per_category: Number of articles per category
        
    Returns:
        Dictionary with category as key and list of articles as value
    """
    categorized_news = {}
    
    for category in categories:
        try:
            params = {
                'q': f'india AND {category}',
                'language': 'en',
                'sortBy': 'publishedAt',
                'apiKey': NEWS_API_KEY,
                'pageSize': articles_per_category
            }
            
            logger.info(f"Fetching news for category: {category}")
            response = requests.get(NEWS_API_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'ok':
                articles = data.get('articles', [])
                categorized_news[category] = articles[:articles_per_category]
                logger.info(f"Fetched {len(categorized_news[category])} articles for {category}")
            else:
                logger.error(f"NewsAPI error for {category}: {data.get('message')}")
                categorized_news[category] = []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching news for {category}: {e}")
            categorized_news[category] = []
        except Exception as e:
            logger.error(f"Unexpected error in fetch_news for {category}: {e}")
            categorized_news[category] = []
    
    return categorized_news


def format_categorized_news(categorized_news: Dict[str, List[Dict]]) -> str:
    """
    Format categorized news into a readable briefing script.
    Shows only trending topic titles (no summaries).
    
    Args:
        categorized_news: Dictionary with categories and their articles
        
    Returns:
        Formatted news briefing text with titles only
    """
    briefing_parts = []
    
    category_names = {
        'technology': 'Technology News',
        'business': 'Business News',
        'general': 'General News'
    }
    
    for category, articles in categorized_news.items():
        if not articles:
            continue
            
        category_title = category_names.get(category, category.title())
        briefing_parts.append(f"\n\n📌 {category_title}:")
        
        for i, article in enumerate(articles[:15], 1):
            title = article.get('title', 'No title')
            briefing_parts.append(f"\n{i}. {title}")
    
    return " ".join(briefing_parts)


def create_briefing_script(categorized_news: Dict[str, List[Dict]]) -> str:
    """
    Create a friendly briefing script with intro and outro.
    
    Args:
        categorized_news: Dictionary with categories and their articles
        
    Returns:
        Complete briefing script
    """
    current_date = datetime.now().strftime("%B %d, %Y")
    
    intro = f"Good morning gouthami! Here is your daily news briefing for {current_date}. "
    
    news_content = format_categorized_news(categorized_news)
    
    outro = " That's all for today's news briefing. Have a great day ahead!"
    
    script = intro + news_content + outro
    return script


def generate_audio(text: str, output_file: str = "news.mp3") -> bool:
    """
    Convert text to speech using gTTS with Indian accent.
    Uses slow=False for faster, more natural speech.
    
    Args:
        text: Text to convert to speech
        output_file: Output audio file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Generating audio from text using gTTS (Indian English, fast mode)")
        
        tts = gTTS(text=text, lang='en', tld='co.in', slow=False)
        tts.save(output_file)
        
        logger.info(f"Audio saved to {output_file} (Indian accent, fast speech)")
        return True
        
    except Exception as e:
        logger.error(f"Error generating audio: {e}")
        return False


async def send_telegram_message(text: str, audio_file: Optional[str] = None) -> bool:
    """
    Send message and audio to Telegram chat.
    Splits long messages into multiple parts if needed.
    
    Args:
        text: Text message to send
        audio_file: Path to audio file (optional)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        MAX_LENGTH = 4096
        
        if len(text) > MAX_LENGTH:
            logger.info(f"Message too long ({len(text)} chars), splitting into parts")
            parts = []
            current_part = ""
            
            for line in text.split('\n'):
                if len(current_part) + len(line) + 1 < MAX_LENGTH:
                    current_part += line + '\n'
                else:
                    if current_part:
                        parts.append(current_part)
                    current_part = line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts, 1):
                logger.info(f"Sending text message part {i}/{len(parts)} to Telegram")
                await bot.send_message(chat_id=CHAT_ID, text=part)
        else:
            logger.info("Sending text message to Telegram")
            await bot.send_message(chat_id=CHAT_ID, text=text)
        
        if audio_file and os.path.exists(audio_file):
            logger.info("Sending audio file to Telegram")
            with open(audio_file, 'rb') as audio:
                await bot.send_audio(
                    chat_id=CHAT_ID,
                    audio=audio,
                    title="Daily News Briefing",
                    performer="News Bot"
                )
        
        logger.info("Successfully sent Telegram messages")
        return True
        
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False


async def run_daily_briefing():
    """
    Main function to run the daily news briefing workflow.
    """
    try:
        logger.info("=" * 50)
        logger.info("Starting daily news briefing")
        logger.info("=" * 50)
        
        categorized_news = fetch_news_by_category(
            categories=['technology', 'business', 'general'],
            articles_per_category=15
        )
        
        total_articles = sum(len(articles) for articles in categorized_news.values())
        
        if total_articles == 0:
            error_msg = "Failed to fetch news articles. Please check your NewsAPI key and connection. Note: NewsAPI free tier may have restrictions."
            logger.error(error_msg)
            await send_telegram_message(f"❌ {error_msg}")
            return
        
        logger.info(f"Fetched total {total_articles} articles across all categories")
        
        briefing_script = create_briefing_script(categorized_news)
        logger.info(f"Created briefing script ({len(briefing_script)} characters)")
        
        audio_file = "news.mp3"
        audio_success = generate_audio(briefing_script, audio_file)
        
        if audio_success:
            await send_telegram_message(
                text=f"📰 *Daily News Briefing*\n\n{briefing_script}",
                audio_file=audio_file
            )
        else:
            await send_telegram_message(
                text=f"📰 *Daily News Briefing*\n\n{briefing_script}\n\n⚠️ Audio generation failed."
            )
        
        if os.path.exists(audio_file):
            os.remove(audio_file)
            logger.info("Cleaned up audio file")
        
        logger.info("Daily briefing completed successfully")
        
    except Exception as e:
        logger.error(f"Error in run_daily_briefing: {e}")
        try:
            await send_telegram_message(f"❌ Error generating daily briefing: {str(e)}")
        except:
            pass


async def test_briefing():
    """
    Test function to run briefing immediately.
    """
    logger.info("Running test briefing...")
    await run_daily_briefing()


def main():
    """
    Main entry point - sets up scheduler and runs the bot.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    
    if not all([NEWS_API_KEY, TELEGRAM_BOT_TOKEN, CHAT_ID]):
        logger.error("Missing required environment variables. Please check your .env file.")
        return
    
    logger.info("Starting Telegram News Bot")
    logger.info(f"Scheduled to run daily at 07:00 AM")
    
    scheduler = AsyncIOScheduler()
    
    scheduler.add_job(
        run_daily_briefing,
        trigger='cron',
        hour=7,
        minute=0,
        id='daily_news_briefing',
        name='Daily News Briefing at 7 AM',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started successfully")
    
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down bot...")
        scheduler.shutdown()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_briefing())
    else:
        main()
