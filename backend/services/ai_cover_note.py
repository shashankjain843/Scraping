import logging
from sqlalchemy.orm import Session
from backend.config import settings
from backend.models import Job, User, UserSettings

logger = logging.getLogger("ai_cover_note")

def generate_ai_cover_note(db: Session, user: User, job: Job) -> str:
    """
    Generates a personalized role-specific cover note for Method A (external application link).
    Uses Gemini API if key is available, or structured fallback template if key is missing.
    """
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    gemini_key = (user_settings.gemini_api_key if user_settings and user_settings.gemini_api_key else settings.GEMINI_API_KEY)

    prompt = (
        f"Write a concise, professional, 150-word cover note for a candidate applying to a {job.role_category.replace('_', ' ').title()} "
        f"role titled '{job.title}' at '{job.company}' located in '{job.city}'. "
        f"Candidate Name: {user.full_name}. "
        f"Emphasize technical proficiency in SQL, Python, data analysis, and domain enthusiasm. "
        f"Keep it tailored, professional, and clear."
    )

    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini AI cover note generation error: {str(e)}")

    # Fallback template if Gemini key is missing or failed
    if job.role_category == "data_analyst":
        return (
            f"Dear Hiring Team at {job.company},\n\n"
            f"I am writing to express my strong interest in the {job.title} position in {job.city}. "
            f"With a solid background in data analysis, SQL query development, Python data manipulation, "
            f"and dashboard building, I am confident in my ability to analyze key metrics and support data-driven decision making.\n\n"
            f"I look forward to discussing how my analytical skills can contribute to {job.company}.\n\n"
            f"Best regards,\n{user.full_name}"
        )
    else:
        return (
            f"Dear Hiring Manager,\n\n"
            f"I am excited to apply for the {job.title} role at {job.company} in {job.city}. "
            f"My technical expertise includes machine learning, Python statistical modeling, SQL data pipelines, "
            f"and problem-solving. I am eager to apply my data science knowledge to solve complex business problems for {job.company}.\n\n"
            f"Thank you for considering my application.\n\n"
            f"Sincerely,\n{user.full_name}"
        )
