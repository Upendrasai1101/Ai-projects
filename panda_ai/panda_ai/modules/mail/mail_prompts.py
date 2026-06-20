# FILE: modules/mail/mail_prompts.py


def build_pitch_prompt(data: dict) -> str:
    """
    Cold email prompt for job seekers and freelancers.
    All fields pulled from the request body dict.
    Missing fields fall back to safe defaults.
    """
    return f"""Write a professional cold email for a job application.

Sender details:
  Name         : {data.get('sender_name',    'Applicant')}
  Role / Title : {data.get('sender_role',    'Developer')}
  Skills       : {data.get('skills',         'Not specified')}
  Key project  : {data.get('project_name',   'Not specified')}
  College      : {data.get('college',        'Not specified')}
  Target job   : {data.get('job_target',     'Software Developer')}

Recipient: {data.get('recipient_role', 'Hiring Manager')}

Rules:
- Include a Subject: line at the top
- Professional but warm tone
- Mention the key project naturally in the body
- Maximum 3 short paragraphs
- End with a clear call-to-action
- Do NOT use placeholders like [Company Name]
- No bullet points inside the email body
- Output ONLY the email text, no explanation"""


def build_draft_prompt(data: dict) -> str:
    """
    Formal draft prompt for general professional communication.
    Examples: leave applications, escalations, requests.
    """
    tone = data.get("tone", "formal")
    return f"""Write a {tone} professional email.

Details:
  Subject : {data.get('subject',     'Not specified')}
  Context : {data.get('context',     'Not specified')}
  From    : {data.get('sender_name', 'The Sender')}

Rules:
- Include Subject: line at the top
- Appropriate {tone} salutation and sign-off
- Clear, concise body — no filler phrases
- Maximum 2-3 paragraphs
- Output ONLY the email text, no explanation"""
