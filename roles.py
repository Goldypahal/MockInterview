"""Interview roles and what the interviewer should focus on for each."""

ROLES = {
    "Python Developer": "Python fundamentals (data types, OOP, decorators, generators), error handling, "
                        "standard library, writing clean code, basic SQL, Git, simple problem solving.",
    "Data Analyst": "SQL (joins, GROUP BY, window functions), Excel, statistics basics, data cleaning, "
                    "pandas, visualisation and dashboards, explaining insights to non-technical people.",
    "Machine Learning Engineer": "ML fundamentals (bias/variance, overfitting, metrics), common algorithms, "
                                 "feature engineering, model evaluation, neural network basics, deploying a model, "
                                 "projects on the candidate's resume.",
    "AI / GenAI Engineer": "LLM basics, prompt engineering, RAG, AI agents and tool use, evaluation, "
                           "responsible AI, cloud AI services (Azure AI / Gemini / OpenAI), projects.",
    "Software Development Engineer (SDE)": "Data structures and algorithms (arrays, strings, hashing, trees, "
                                           "graphs), time and space complexity, OOP, DBMS, OS and networking basics.",
    "Web Developer (Full Stack)": "HTML/CSS/JavaScript, React, Node.js/Express, REST APIs, databases "
                                  "(SQL and MongoDB), authentication, deployment.",
    "Java Developer": "Core Java, OOP, collections, exceptions, multithreading basics, JDBC, Spring Boot basics.",
    "Cloud / DevOps Engineer": "Linux, networking basics, cloud services (Azure/AWS), Docker, CI/CD, "
                               "monitoring, Infrastructure as Code basics.",
    "HR Round (any role)": "Self-introduction, strengths and weaknesses, teamwork, conflict handling, "
                           "goals, why this company, handling pressure, situational (STAR) questions.",
}

LEVELS = ["Fresher / Intern", "0–2 years experience", "2–5 years experience"]

INTERVIEW_TYPES = {
    "Technical": "Ask mainly technical questions for the role, from easy to medium difficulty.",
    "HR / Behavioural": "Ask behavioural and HR questions. Encourage STAR-format (Situation, Task, "
                        "Action, Result) answers.",
    "Mixed": "Mix technical questions with one or two behavioural questions, like a real campus placement round.",
}
