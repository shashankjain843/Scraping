"""
template_generator.py
Auto-generates professional email subject + body templates from a resume file.
Uses rule-based skill extraction (no external API needed).
If GEMINI_API_KEY is configured, optionally uses Gemini for more personalized output.
"""
import os
import re
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Skill keyword lists per role
# ---------------------------------------------------------------------------
DA_SKILLS = [
    "SQL", "MySQL", "PostgreSQL", "Excel", "Power BI", "Tableau", "Python",
    "Pandas", "NumPy", "ETL", "Data Visualization", "Data Cleaning",
    "Dashboard", "Reporting", "Pivot Table", "VLOOKUP", "Statistics",
    "Data Analysis", "Business Intelligence", "R", "SSRS", "Looker",
]

DS_SKILLS = [
    "Python", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
    "Scikit-Learn", "NLP", "Natural Language Processing", "Statistics",
    "Data Science", "SQL", "Pandas", "NumPy", "Feature Engineering",
    "Neural Network", "Classification", "Regression", "Clustering",
    "Computer Vision", "Model Deployment", "MLOps", "A/B Testing",
    "Big Data", "Spark", "Hadoop", "Keras",
]


def _extract_text_from_resume(file_path: str) -> str:
    """Extracts raw text from PDF or DOCX resume."""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == ".docx":
            import docx
            doc = docx.Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext in (".pdf",):
            with open(file_path, "rb") as f:
                content = f.read().decode("latin1", errors="ignore")
            text = re.sub(r'[\r\n]+', '\n', content)[:5000]
    except Exception:
        pass
    return text


def _extract_matching_skills(text: str, skill_list: list) -> list:
    """Returns skills from skill_list that appear in the resume text (case-insensitive)."""
    found = []
    text_lower = text.lower()
    for skill in skill_list:
        if skill.lower() in text_lower:
            found.append(skill)
    return found


def _extract_candidate_name(text: str, default_name: str) -> str:
    """Best-effort name extraction from resume top lines."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines[:15]:
        if re.search(r'\b(?:resume|cv|curriculum|profile|email|phone|contact|address)\b', line, re.IGNORECASE):
            continue
        if re.match(r'^[A-Z][a-zA-Z\.\'\-]{1,20}(?:\s+[A-Z][a-zA-Z\.\'\-]{1,20}){1,3}$', line):
            return line
    return default_name or "Applicant"


def auto_generate_template_from_resume(
    resume_path: str,
    role_category: str,
    user_full_name: str = "",
) -> Tuple[str, str]:
    """
    Reads resume file, extracts relevant skills, and auto-generates
    a professional email subject + body template for the given role.

    Returns (subject_template, body_template) with {{placeholders}} intact.
    """
    text = _extract_text_from_resume(resume_path)
    candidate_name = _extract_candidate_name(text, user_full_name)

    if role_category == "data_analyst":
        skills_found = _extract_matching_skills(text, DA_SKILLS)
        subject = "Application for {{job_title}} – {{user_name}}"
        if skills_found:
            skills_str = ", ".join(skills_found[:5])
            body = (
                "Dear Hiring Manager,\n\n"
                "I am writing to express my strong interest in the {{job_title}} role at {{company}} in {{city}}.\n\n"
                f"With hands-on experience in {skills_str}, I have developed the analytical skills needed "
                "to transform raw data into actionable business insights. I am adept at building dashboards, "
                "writing complex SQL queries, and presenting data-driven findings to stakeholders.\n\n"
                "I am excited about the opportunity to bring my skills to {{company}} and contribute to "
                "your data initiatives. Please find my resume attached for your review.\n\n"
                "I would welcome the chance to discuss how my background aligns with your team's needs.\n\n"
                "Sincerely,\n"
                "{{user_name}}\n"
                "{{user_email}}"
            )
        else:
            body = (
                "Dear Hiring Manager,\n\n"
                "I am writing to apply for the {{job_title}} position at {{company}} in {{city}}.\n\n"
                "My background includes strong proficiency in SQL, Python, and data visualization tools "
                "such as Power BI and Tableau. I have experience performing data cleaning, ETL pipelines, "
                "and building automated reporting dashboards that drive decision-making.\n\n"
                "I am particularly drawn to {{company}} because of the opportunity to work with real-world "
                "data at scale. Please find my resume attached for your consideration.\n\n"
                "Thank you for your time, and I look forward to the opportunity to connect.\n\n"
                "Sincerely,\n"
                "{{user_name}}\n"
                "{{user_email}}"
            )

    else:  # data_scientist
        skills_found = _extract_matching_skills(text, DS_SKILLS)
        subject = "Application for {{job_title}} Position – {{user_name}}"
        if skills_found:
            skills_str = ", ".join(skills_found[:5])
            body = (
                "Dear Hiring Team,\n\n"
                "I am reaching out to apply for the {{job_title}} position at {{company}} in {{city}}.\n\n"
                f"My experience spans {skills_str}, which I have applied to build predictive models, "
                "conduct exploratory data analysis, and deploy machine learning solutions that create "
                "measurable business value.\n\n"
                "I am confident that my technical depth and ability to communicate insights clearly "
                "would make me a strong contributor to {{company}}'s data science team. "
                "My resume is attached for your review.\n\n"
                "I would be glad to discuss how my experience aligns with your requirements at your convenience.\n\n"
                "Best regards,\n"
                "{{user_name}}\n"
                "{{user_email}}"
            )
        else:
            body = (
                "Dear Hiring Team,\n\n"
                "I am applying for the {{job_title}} position at {{company}} in {{city}}.\n\n"
                "I have a strong foundation in Python, machine learning algorithms, statistical modeling, "
                "and SQL. I have hands-on experience building and evaluating classification, regression, "
                "and clustering models using scikit-learn and TensorFlow.\n\n"
                "I am eager to leverage my skills at {{company}} to deliver data-driven solutions. "
                "Please find my resume attached for your reference.\n\n"
                "Thank you for considering my application. I look forward to hearing from you.\n\n"
                "Best regards,\n"
                "{{user_name}}\n"
                "{{user_email}}"
            )

    return subject, body
