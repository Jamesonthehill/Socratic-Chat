from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "rag" / "software-engineering-3155-fall-2026"
RAW_DOCS_DIR = ROOT / "backend" / "data" / "raw_docs"

COURSE = {
    "course_id": "software-engineering-3155-fall-2026",
    "course_name": "Software Engineering 3155",
    "term": "Fall 2026",
    "audience": "Students and independent learners",
    "assistant_mode": "Socratic tutoring",
    "language": "English",
}

COURSE_GUIDANCE = {
    "delivery": [
        "The Fall 2026 course is asynchronous online.",
        "Canvas is the authoritative location for the current schedule, official assignment files, announcements, grades, and due dates.",
        "The cleaned RAG corpus intentionally excludes office hours, staff contact details, and meeting links.",
    ],
    "topics": [
        "Software engineering principles and the software development life cycle",
        "Software requirements and software design",
        "Agile development and Scrum",
        "Software testing and test-driven development",
        "Software implementation, security, deployment, and DevOps",
        "Object-oriented programming and version control",
        "Web development, APIs, databases, and full-stack development",
        "Containerization, Docker, cloud computing, and machine learning",
    ],
    "module_structure": [
        "Preparation work may include installing tools, following guidelines, and completing surveys.",
        "Lecture material covers concepts, theory, and professional practices.",
        "Recitation material emphasizes practical tasks, assignment preparation, and discussion.",
        "Homework may include programming material, assignments, and quizzes.",
        "Additional resources may include cheat sheets, articles, new technologies, interview preparation, and extra credit.",
    ],
    "tools": [
        "PyCharm",
        "MySQL Workbench",
        "Docker Desktop",
        "Git and GitHub",
        "Optional JetBrains tools such as WebStorm and DataGrip",
    ],
    "grading": [
        "Homework: 30%",
        "Quizzes: 20%",
        "Midterm: 15%",
        "Final project: 30%",
        "Attendance: 5%",
        "Letter grades: A=90–100%, B=80–89%, C=70–79%, D=60–69%, F=0–59%.",
    ],
    "late_policy": [
        "The stated assignment late penalty is 5% per day.",
        "Assignments may be submitted up to one week late with a maximum stated penalty of 30%; after that point the stated result is zero credit.",
        "Quizzes do not allow late submission.",
        "Potential exceptions are handled case by case and require timely communication and appropriate justification through official course channels.",
    ],
    "ai_policy": [
        "Students may not use ChatGPT, GitHub Copilot, or similar AI tools for quizzes.",
        "Students may not use ChatGPT or similar AI tools to generate coding-assignment code from scratch.",
        "For coding assignments, students may use an AI chatbot to debug code they have written.",
        "This chatbot must therefore require the learner to provide their own attempt, reasoning, or error before offering code-level debugging guidance.",
    ],
    "academic_integrity": [
        "Submitted work must be the student's own.",
        "External references used in reports must be cited.",
        "Duplicate or plagiarized work receives no credit and may lead to disciplinary action under the university academic-integrity code.",
    ],
}

SOURCE_NOTES = [
    {
        "id": "se3155-source-note-001",
        "severity": "high",
        "scope": "Assignment 4",
        "note": (
            "The pasted Assignment 4 page omits the example Python code blocks and several example "
            "responses/images. The corpus states the observable endpoint requirements but does not invent "
            "the missing code. Obtain the original linked assignment document before using the chatbot for "
            "line-by-line implementation guidance."
        ),
    },
    {
        "id": "se3155-source-note-002",
        "severity": "medium",
        "scope": "Assignment 4",
        "note": (
            "One sentence says Flask, while the title, package installation, Uvicorn command, interactive "
            "documentation, and remaining instructions consistently specify FastAPI. The corpus treats "
            "FastAPI as authoritative and records Flask as a likely source typo."
        ),
    },
    {
        "id": "se3155-source-note-003",
        "severity": "medium",
        "scope": "Assignment 1",
        "note": (
            "The compact Part 1 function table assigns 4 points per function, but the detailed Canvas rubric "
            "assigns 8 points per function. The detailed rubric totals the stated 40 Part 1 points and is "
            "therefore used as the authoritative scoring interpretation."
        ),
    },
    {
        "id": "se3155-source-note-004",
        "severity": "low",
        "scope": "Assignment 2",
        "note": (
            "The filename sandwich_makerr.py appears once with a doubled r. The surrounding instructions "
            "refer to the sandwich_maker module. The corpus uses sandwich_maker.py and flags the original "
            "spelling for instructor verification."
        ),
    },
    {
        "id": "se3155-source-note-005",
        "severity": "medium",
        "scope": "Assignment 5",
        "note": (
            "The assignment says SQLAlchemy creates five tables and later names sandwiches, resources, "
            "recipes, orders, and order_details. The task text says the orders implementation is supplied "
            "as the example and students implement the other four controllers and endpoint groups."
        ),
    },
    {
        "id": "se3155-source-note-006",
        "severity": "medium",
        "scope": "All assignments",
        "note": (
            "Deadlines, semester-specific Canvas identifiers, private repository invitations, instructor and "
            "TA contact details, and private meeting links are intentionally excluded from this learner corpus."
        ),
    },
]

ASSIGNMENTS = [
    {
        "id": "assignment-1",
        "number": 1,
        "title": "Interactive Ham Sandwich Maker Machine",
        "points": 50,
        "status": "verified_from_pasted_canvas_content",
        "prerequisites": ["Basic Python", "Functions", "Dictionaries", "Loops and conditionals", "Git basics"],
        "objectives": [
            "Build an interactive terminal program without hard-coding scenario outputs.",
            "Check whether sufficient ingredients exist before making a sandwich.",
            "Process coin input, validate payment, and calculate change.",
            "Update and report remaining resources.",
            "Use Git and conventional commit messages in a private GitHub repository.",
        ],
        "requirements": [
            "The user selects a sandwich size.",
            "The program checks available resources before production.",
            "If resources are insufficient, the program reports the shortage and does not make the sandwich.",
            "If resources are sufficient, the program accepts coins and compares the inserted amount with the cost.",
            "The program reports insufficient payment or returns the applicable change.",
            "The user can request a remaining-resource report and turn off the machine.",
            "Complete the supplied skeleton in PyCharm and submit main.py.",
        ],
        "interfaces": [
            {
                "name": "check_resources",
                "signature": "check_resources(ingredients: dict) -> bool",
                "purpose": "Determine whether the machine has enough of every required ingredient.",
            },
            {
                "name": "process_coins",
                "signature": "process_coins() -> float",
                "purpose": "Collect coin quantities and return the total monetary value inserted.",
            },
            {
                "name": "transaction_result",
                "signature": "transaction_result(coins: float, cost: float) -> bool",
                "purpose": "Determine whether payment succeeds and handle insufficient funds or change.",
            },
            {
                "name": "make_sandwich",
                "signature": "make_sandwich(sandwich_size: str, ingredients: dict) -> None",
                "purpose": "Deduct required ingredients and complete the selected sandwich.",
            },
        ],
        "deliverables": ["main.py", "Link to a private GitHub repository"],
        "git_requirements": [
            "Push with Git; manual file upload is not acceptable.",
            "Repository history must contain at least five commits.",
            "Commit messages must follow Conventional Commits.",
        ],
        "rubric": [
            "Program functionality: 8 points.",
            "check_resources: 8 points in the detailed rubric.",
            "process_coins: 8 points in the detailed rubric.",
            "transaction_result: 8 points in the detailed rubric.",
            "make_sandwich: 8 points in the detailed rubric.",
            "GitHub repository and version-control requirements: 10 points.",
        ],
        "socratic_prompts": [
            "What information must be known before the machine can decide whether to make a sandwich?",
            "What should remain unchanged when either resources or payment are insufficient?",
            "What single responsibility does each required function have?",
            "Which test case would reveal that a resource was deducted too early?",
        ],
    },
    {
        "id": "assignment-2",
        "number": 2,
        "title": "Modular Ham Sandwich Maker Machine",
        "points": 30,
        "status": "verified_from_pasted_canvas_content",
        "prerequisites": ["Assignment 1", "Python modules", "Classes and objects", "Imports"],
        "objectives": [
            "Refactor the Assignment 1 program into modules and classes.",
            "Separate production, payment, data, and application-control responsibilities.",
            "Preserve the observable behavior of the Assignment 1 scenario.",
        ],
        "requirements": [
            "Use four files: main.py, data.py, sandwich_maker.py, and cashier.py.",
            "Import data, sandwich_maker, and cashier at the top of main.py.",
            "Create variables from the resources and recipes dictionaries in data.py.",
            "Create instances of SandwichMaker and Cashier; SandwichMaker receives resources through its constructor.",
            "Move check_resources and make_sandwich into SandwichMaker.",
            "Move process_coins and transaction_result into Cashier.",
            "Keep recipes and resources in data.py as temporary in-memory data.",
            "Use main.py as the program entry point and integration layer.",
        ],
        "architecture": [
            "data.py: stores resources and recipes data.",
            "sandwich_maker.py: defines SandwichMaker and all sandwich-production behavior.",
            "cashier.py: defines Cashier and all payment behavior.",
            "main.py: creates objects, receives user commands, and coordinates the modules.",
        ],
        "deliverables": ["GitHub repository link; do not submit a ZIP file"],
        "git_requirements": ["Commit and push all assignment files to GitHub."],
        "rubric": [
            "Module implementation: 6 points.",
            "Code skeleton utilization: 6 points.",
            "Class and function migration: 6 points.",
            "Program functionality and integration: 6 points.",
            "Code quality and conventions: 6 points.",
        ],
        "socratic_prompts": [
            "Which responsibilities in Assignment 1 naturally belong together?",
            "Which object needs access to resources, and why should that dependency be passed to its constructor?",
            "What should main.py coordinate without implementing itself?",
            "How can you verify that refactoring changed structure but not behavior?",
        ],
    },
    {
        "id": "assignment-3",
        "number": 3,
        "title": "Sandwich Maker Database",
        "points": 50,
        "status": "verified_from_pasted_canvas_content",
        "prerequisites": ["Assignments 1 and 2", "Basic SQL", "MySQL", "Relational tables"],
        "objectives": [
            "Create a MySQL database for the Sandwich Maker domain.",
            "Represent resources, sandwich prices, and recipes as relational tables.",
            "Insert supplied seed data and verify it with SELECT queries.",
        ],
        "requirements": [
            "Install MySQL and MySQL Workbench.",
            "Create a database using an explicit database-creation statement.",
            "Create resources, sandwiches, and recipes tables using the required columns and types.",
            "Insert all supplied seed data.",
            "Execute a SELECT statement for each table and capture its result.",
        ],
        "schema": [
            "resources(item VARCHAR(50), amount INT)",
            "sandwiches(sandwich_size VARCHAR(50), price DECIMAL(5,2))",
            "recipes(sandwich_size VARCHAR(50), item VARCHAR(50), amount INT)",
        ],
        "seed_data": {
            "resources": [
                {"item": "bread", "amount": 12},
                {"item": "ham", "amount": 18},
                {"item": "cheese", "amount": 24},
            ],
            "sandwiches": [
                {"sandwich_size": "small", "price": 1.75},
                {"sandwich_size": "medium", "price": 3.25},
                {"sandwich_size": "large", "price": 5.50},
            ],
            "recipes": [
                {"sandwich_size": "small", "item": "bread", "amount": 2},
                {"sandwich_size": "small", "item": "ham", "amount": 4},
                {"sandwich_size": "small", "item": "cheese", "amount": 4},
                {"sandwich_size": "medium", "item": "bread", "amount": 4},
                {"sandwich_size": "medium", "item": "ham", "amount": 6},
                {"sandwich_size": "medium", "item": "cheese", "amount": 8},
                {"sandwich_size": "large", "item": "bread", "amount": 6},
                {"sandwich_size": "large", "item": "ham", "amount": 8},
                {"sandwich_size": "large", "item": "cheese", "amount": 12},
            ],
        },
        "deliverables": [
            "One .sql file containing all database, CREATE TABLE, INSERT, and SELECT statements.",
            "Three screenshots: one SELECT result for each table.",
        ],
        "rubric": [
            "Database creation statement: 2 points.",
            "Three CREATE TABLE statements: 15 points.",
            "Three groups of INSERT statements: 18 points.",
            "Three SELECT statements: 3 points.",
            "Three table-result screenshots: 12 points.",
        ],
        "socratic_prompts": [
            "Which facts describe inventory, which describe products, and which connect products to ingredients?",
            "Why does one sandwich size require several rows in recipes?",
            "Which SQL query would prove that every required seed row was inserted?",
            "What data problem could occur if size names use inconsistent capitalization?",
        ],
    },
    {
        "id": "assignment-4",
        "number": 4,
        "title": "FastAPI Implementation",
        "points": 15,
        "status": "partially_verified_missing_source_code_blocks",
        "prerequisites": ["Python functions", "HTTP basics", "Virtual environments"],
        "objectives": [
            "Create and run a simple FastAPI application.",
            "Understand routes, HTTP GET and PUT methods, path parameters, query parameters, and request bodies.",
            "Use Pydantic-compatible Python types for a request body.",
            "Use FastAPI's generated interactive API documentation to exercise endpoints.",
        ],
        "requirements": [
            "Install fastapi and uvicorn[standard] in the project virtual environment.",
            "Create main.py containing the assignment's FastAPI application code; the pasted source does not include that code block.",
            "Run the application with: uvicorn main:app --reload.",
            "Provide GET routes at / and /items/{item_id}.",
            "The item_id path parameter must be an integer.",
            "The /items/{item_id} route accepts an optional string query parameter named q.",
            "Add a request-body model and a PUT route as directed by the original assignment; the pasted source omits the model and route code.",
            "Use http://127.0.0.1:8000/docs and run every required request.",
        ],
        "verification": [
            "For Part 1, capture one screenshot for each GET endpoint, including parameters and response body.",
            "For Part 2, execute the PUT request through interactive API docs and capture the required result.",
            "Run all requests required by both parts.",
        ],
        "deliverables": [
            "GitHub repository containing complete source code and main.py in the assignment folder.",
            "Screenshots from the interactive API docs for the required requests.",
        ],
        "git_requirements": [
            "At least three commits are required.",
            "Commit messages must follow Conventional Commits.",
            "The final commit must precede the assignment submission time.",
            "A source instruction says to invite the course TAs as collaborators; identifying information is excluded from this corpus.",
        ],
        "rubric": [
            "main.py correctness: 5 points.",
            "Required screenshots and experimentation: 7 points.",
            "GitHub submission: 3 points.",
        ],
        "socratic_prompts": [
            "Which part of the URL identifies the resource, and which part supplies an optional value?",
            "Why must item_id be declared as an integer?",
            "What changes between a GET request and a PUT request with a body?",
            "What evidence in the interactive documentation demonstrates that an endpoint works?",
        ],
    },
    {
        "id": "assignment-5",
        "number": 5,
        "title": "CRUD Operations in FastAPI",
        "points": 80,
        "status": "verified_from_assignment_page_7_and_pasted_canvas_content",
        "prerequisites": ["Assignments 2 through 4", "FastAPI", "SQLAlchemy", "MySQL", "Pydantic schemas", "REST CRUD"],
        "objectives": [
            "Build a modular database-backed FastAPI application.",
            "Connect FastAPI to a MySQL database using SQLAlchemy and PyMySQL.",
            "Implement Create, Read, Update, and Delete operations for required domain tables.",
            "Separate controllers, persistence models, API schemas, dependencies, and routes.",
        ],
        "setup": [
            "Start from the code base supplied on the assignment page.",
            "Install fastapi, uvicorn[standard], sqlalchemy, and pymysql in the virtual environment.",
            "Create a MySQL database named sandwich_maker_api.",
            "Configure the database name, MySQL username, and password in api/dependencies/config.py.",
            "From the assignment directory run: uvicorn api.main:app --reload.",
            "On startup, SQLAlchemy should create five tables: sandwiches, resources, recipes, orders, and order_details.",
        ],
        "architecture": [
            "api/controllers/: one controller module per table; controller functions perform database CRUD operations.",
            "api/models/models.py: SQLAlchemy classes describing database tables and relationships.",
            "api/models/schemas.py: request and response schemas used by the API.",
            "api/dependencies/config.py: database and project configuration values.",
            "api/dependencies/database.py: database engine, session, and connection handling.",
            "api/main.py: FastAPI entry point and route definitions that delegate work to controllers.",
        ],
        "requirements": [
            "Use the supplied orders controller and routes as the implementation pattern.",
            "Create controller modules for sandwiches, resources, recipes, and order_details.",
            "For each required table implement create, read_all, read_one, update, and delete.",
            "Add corresponding POST, GET collection, GET item, PUT, and DELETE endpoints in api/main.py.",
            "Use paths, parameter names, schema types, response models, and tags appropriate to each table.",
            "Return 404 when a requested record does not exist.",
            "Verify every endpoint using http://127.0.0.1:8000/docs.",
        ],
        "crud_contracts": [
            "create: instantiate the SQLAlchemy model, add it to the session, commit, refresh, and return it.",
            "read_all: query the table and return all rows.",
            "read_one: filter by the record identifier and return the first match or None.",
            "update: locate the record, apply only supplied fields, commit, and return the updated row.",
            "delete: locate and delete the record, commit, and return HTTP 204 No Content.",
        ],
        "deliverables": ["GitHub repository containing complete source code in the assignment folder"],
        "git_requirements": [
            "Commit and push the work; manual upload is not an equivalent substitute.",
            "Commit messages must follow Conventional Commits.",
            "The final commit must precede the assignment submission time.",
        ],
        "rubric": [
            "Table/schema implementation for sandwiches, resources, recipes, and order_details: 8 points each (32 total).",
            "CRUD endpoint implementation for sandwiches, resources, recipes, and order_details: 10 points each (40 total).",
            "Repository submission and pushed source code: 8 points.",
        ],
        "socratic_prompts": [
            "Which layer should know SQLAlchemy, and which layer should know HTTP routes?",
            "How can the supplied orders implementation serve as a pattern without copying table-specific names incorrectly?",
            "What should read_one return when the database contains no matching row, and which layer converts that into HTTP 404?",
            "Why should an update schema distinguish omitted fields from fields explicitly set by the client?",
            "Which sequence of API requests would verify a complete CRUD lifecycle?",
        ],
    },
]


def common_meta() -> dict[str, object]:
    return {
        "course_id": COURSE["course_id"],
        "course_name": COURSE["course_name"],
        "term": COURSE["term"],
        "audience": COURSE["audience"],
        "language": COURSE["language"],
        "access_level": "course_learners",
        "contains_private_contact_information": False,
    }


def chunk(
    chunk_id: str,
    title: str,
    content_type: str,
    content: str,
    *,
    assignment: dict[str, object] | None = None,
    topics: list[str] | None = None,
    keywords: list[str] | None = None,
    confidence: str = "verified",
    needs_instructor_verification: bool = False,
) -> dict[str, object]:
    item: dict[str, object] = {
        **common_meta(),
        "chunk_id": chunk_id,
        "title": title,
        "content_type": content_type,
        "topics": topics or [],
        "keywords": keywords or [],
        "academic_integrity_mode": "guided_help_only",
        "confidence": confidence,
        "needs_instructor_verification": needs_instructor_verification,
        "content": content.strip(),
    }
    if assignment:
        item["assignment_id"] = assignment["id"]
        item["assignment_number"] = assignment["number"]
        item["assignment_title"] = assignment["title"]
    return item


def prose_list(label: str, values: list[str]) -> str:
    return f"{label}: " + " ".join(f"{index + 1}) {value}" for index, value in enumerate(values))


def build_chunks() -> list[dict[str, object]]:
    chunks = [
        chunk(
            "se3155-course-identity",
            "Software Engineering 3155: course identity and learning path",
            "course_overview",
            (
                "Software Engineering 3155, Fall 2026, is represented in this corpus as a five-assignment "
                "learning sequence. Assignment 1 builds a procedural interactive Python sandwich-maker. "
                "Assignment 2 refactors it into modules and classes. Assignment 3 moves domain data into a "
                "MySQL relational database. Assignment 4 introduces FastAPI routes, HTTP parameters, request "
                "bodies, and interactive API documentation. Assignment 5 combines modular architecture, "
                "FastAPI, SQLAlchemy, MySQL, Pydantic schemas, and full CRUD endpoints."
            ),
            topics=["course progression", "software engineering", "sandwich maker"],
            keywords=["SE 3155", "Fall 2026", "Python", "Git", "MySQL", "FastAPI", "SQLAlchemy", "CRUD"],
        ),
        chunk(
            "se3155-socratic-policy",
            "Socratic tutoring and academic-integrity policy",
            "tutoring_policy",
            (
                "The chatbot supports students through Socratic questioning. It should first identify the "
                "student's current reasoning, then ask one focused question at a time. If the student is stuck, "
                "it should move through progressively stronger hints, a partial explanation, and only then a "
                "direct explanation. It should finish by asking the student to explain or apply the concept. "
                "For active graded work, it may clarify requirements, explain concepts, diagnose errors, review "
                "student-provided reasoning, and offer analogous examples. Course policy prohibits AI use for "
                "quizzes and prohibits generating coding-assignment code from scratch. Code-level help must be "
                "limited to debugging a learner's own attempt. The chatbot should not produce a complete "
                "ready-to-submit solution, fabricate missing assignment requirements, expose answer keys, or "
                "claim that an inferred detail is verified."
            ),
            topics=["Socratic questioning", "academic integrity", "scaffolding"],
            keywords=["guided questions", "hints", "graded assignment", "no complete solution", "reflection"],
        ),
    ]

    for key, title, content_type, topics, keywords in [
        ("delivery", "Course delivery and source authority", "course_logistics", ["asynchronous course", "Canvas"], ["online", "Canvas", "Fall 2026"]),
        ("topics", "Course subject coverage", "course_topics", ["software engineering topics"], ["requirements", "design", "testing", "Scrum", "DevOps", "cloud", "machine learning"]),
        ("module_structure", "Course module structure", "course_structure", ["learning activities"], ["preparation", "lecture", "recitation", "homework"]),
        ("tools", "Course development tools", "course_tools", ["development environment"], ["PyCharm", "MySQL Workbench", "Docker", "GitHub"]),
        ("grading", "Course grading breakdown", "grading_policy", ["grading"], ["homework", "quizzes", "midterm", "final project", "attendance"]),
        ("late_policy", "Assignment and quiz late policy", "late_policy", ["late submissions"], ["late penalty", "one week", "quiz"]),
        ("ai_policy", "Course AI-use policy", "academic_integrity_policy", ["AI use", "academic integrity"], ["ChatGPT", "Copilot", "quiz", "debugging", "code generation"]),
        ("academic_integrity", "Academic integrity requirements", "academic_integrity_policy", ["academic integrity"], ["own work", "citation", "plagiarism"]),
    ]:
        chunks.append(
            chunk(
                f"se3155-course-{key.replace('_', '-')}",
                title,
                content_type,
                prose_list(title, COURSE_GUIDANCE[key]),
                topics=topics,
                keywords=keywords,
            )
        )

    for assignment in ASSIGNMENTS:
        base = f"se3155-a{assignment['number']}"
        summary_parts = [
            f"Assignment {assignment['number']}: {assignment['title']} is worth {assignment['points']} points.",
            prose_list("Learning objectives", assignment["objectives"]),
            prose_list("Prerequisites", assignment["prerequisites"]),
        ]
        chunks.append(
            chunk(
                f"{base}-overview",
                f"Assignment {assignment['number']} overview and objectives",
                "assignment_overview",
                " ".join(summary_parts),
                assignment=assignment,
                topics=[str(assignment["title"]), "learning objectives"],
                keywords=[f"Assignment {assignment['number']}", "overview", "objectives"],
                confidence="partial" if str(assignment["status"]).startswith("partially") else "verified",
                needs_instructor_verification=str(assignment["status"]).startswith("partially"),
            )
        )

        if assignment.get("setup"):
            chunks.append(
                chunk(
                    f"{base}-setup",
                    f"Assignment {assignment['number']} setup and execution",
                    "setup_instructions",
                    prose_list("Required setup", assignment["setup"]),
                    assignment=assignment,
                    topics=["environment setup", "execution"],
                    keywords=["install", "run", "database", "uvicorn", "configuration"],
                )
            )

        requirements = assignment.get("requirements", [])
        chunks.append(
            chunk(
                f"{base}-requirements",
                f"Assignment {assignment['number']} functional requirements",
                "assignment_requirements",
                prose_list("Requirements", requirements),
                assignment=assignment,
                topics=["functional requirements", str(assignment["title"])],
                keywords=[f"Assignment {assignment['number']}", "requirements", "must", "implementation"],
                confidence="partial" if assignment["number"] == 4 else "verified",
                needs_instructor_verification=assignment["number"] == 4,
            )
        )

        for field, content_type, label in [
            ("interfaces", "function_contracts", "Required function contracts"),
            ("architecture", "software_architecture", "Required architecture"),
            ("schema", "database_schema", "Required database schema"),
            ("crud_contracts", "crud_contracts", "CRUD operation contracts"),
            ("verification", "verification_procedure", "Verification requirements"),
        ]:
            values = assignment.get(field)
            if not values:
                continue
            if field == "interfaces":
                rendered = " ".join(
                    f"{index + 1}) {value['signature']}. Purpose: {value['purpose']}"
                    for index, value in enumerate(values)
                )
            else:
                rendered = prose_list(label, values)
            chunks.append(
                chunk(
                    f"{base}-{field.replace('_', '-')}",
                    f"Assignment {assignment['number']} {label.lower()}",
                    content_type,
                    rendered,
                    assignment=assignment,
                    topics=[label, str(assignment["title"])],
                    keywords=[field.replace("_", " "), "structure", "contract"],
                )
            )

        if assignment.get("seed_data"):
            seed = assignment["seed_data"]
            seed_text = (
                "Required seed data. Resources: "
                + ", ".join(f"{row['item']}={row['amount']}" for row in seed["resources"])
                + ". Sandwich prices: "
                + ", ".join(f"{row['sandwich_size']}=${row['price']:.2f}" for row in seed["sandwiches"])
                + ". Recipe rows: "
                + "; ".join(
                    f"{row['sandwich_size']} uses {row['amount']} {row['item']}"
                    for row in seed["recipes"]
                )
                + "."
            )
            chunks.append(
                chunk(
                    f"{base}-seed-data",
                    f"Assignment {assignment['number']} required seed data",
                    "seed_data",
                    seed_text,
                    assignment=assignment,
                    topics=["database seed data", "resources", "recipes", "sandwich prices"],
                    keywords=["bread", "ham", "cheese", "small", "medium", "large", "INSERT"],
                )
            )

        assessment_text = " ".join(
            [
                prose_list("Deliverables", assignment["deliverables"]),
                prose_list("Version-control requirements", assignment.get("git_requirements", []))
                if assignment.get("git_requirements")
                else "",
                prose_list("Rubric", assignment["rubric"]),
            ]
        )
        chunks.append(
            chunk(
                f"{base}-assessment",
                f"Assignment {assignment['number']} deliverables and rubric",
                "assessment",
                assessment_text,
                assignment=assignment,
                topics=["deliverables", "rubric", "Git"],
                keywords=["submit", "points", "rubric", "GitHub", "commit"],
            )
        )

        chunks.append(
            chunk(
                f"{base}-socratic",
                f"Assignment {assignment['number']} Socratic tutoring prompts",
                "socratic_prompt_bank",
                prose_list("Recommended guiding questions", assignment["socratic_prompts"]),
                assignment=assignment,
                topics=["Socratic questions", str(assignment["title"])],
                keywords=["diagnose", "guide", "reflect", "question"],
            )
        )

    for note in SOURCE_NOTES:
        chunks.append(
            chunk(
                note["id"],
                f"Source-quality note: {note['scope']}",
                "source_quality_note",
                note["note"],
                topics=["source quality", note["scope"]],
                keywords=["missing", "inconsistency", "verification", "source note"],
                confidence="inferred",
                needs_instructor_verification=True,
            )
        )
    return chunks


def markdown_document(chunks: list[dict[str, object]]) -> str:
    lines = [
        "---",
        f"course_id: {COURSE['course_id']}",
        f"course_name: {COURSE['course_name']}",
        f"term: {COURSE['term']}",
        "document_type: rag_core_documentation",
        "privacy: excludes_private_course_contacts",
        "---",
        "",
        f"# {COURSE['course_name']} — {COURSE['term']}",
        "",
        "## Purpose and tutoring policy",
        "",
        next(item["content"] for item in chunks if item["chunk_id"] == "se3155-socratic-policy"),
        "",
        "## Course learning path",
        "",
        next(item["content"] for item in chunks if item["chunk_id"] == "se3155-course-identity"),
        "",
    ]

    for key, heading in [
        ("delivery", "Course delivery and source authority"),
        ("topics", "Course subject coverage"),
        ("module_structure", "Module structure"),
        ("tools", "Development tools"),
        ("grading", "Grading"),
        ("late_policy", "Late policy"),
        ("ai_policy", "AI-use policy"),
        ("academic_integrity", "Academic integrity"),
    ]:
        lines.extend([f"## {heading}", "", *[f"- {value}" for value in COURSE_GUIDANCE[key]], ""])

    for assignment in ASSIGNMENTS:
        lines.extend(
            [
                f"## Assignment {assignment['number']}: {assignment['title']}",
                "",
                f"**Points:** {assignment['points']}  ",
                f"**Source status:** {assignment['status']}",
                "",
                "### Learning objectives",
                "",
                *[f"- {value}" for value in assignment["objectives"]],
                "",
                "### Prerequisites",
                "",
                *[f"- {value}" for value in assignment["prerequisites"]],
                "",
            ]
        )
        for key, heading in [
            ("setup", "Setup"),
            ("requirements", "Requirements"),
            ("architecture", "Architecture"),
            ("schema", "Database schema"),
            ("crud_contracts", "CRUD contracts"),
            ("verification", "Verification"),
            ("deliverables", "Deliverables"),
            ("git_requirements", "Version-control requirements"),
            ("rubric", "Rubric"),
            ("socratic_prompts", "Suggested Socratic prompts"),
        ]:
            values = assignment.get(key)
            if not values:
                continue
            lines.extend([f"### {heading}", "", *[f"- {value}" for value in values], ""])

        if assignment.get("interfaces"):
            lines.extend(["### Required function contracts", ""])
            for interface in assignment["interfaces"]:
                lines.append(f"- `{interface['signature']}` — {interface['purpose']}")
            lines.append("")

        if assignment.get("seed_data"):
            lines.extend(["### Required seed data", ""])
            for table_name, rows in assignment["seed_data"].items():
                lines.append(f"#### {table_name}")
                lines.append("")
                for row in rows:
                    lines.append("- " + ", ".join(f"{key}={value}" for key, value in row.items()))
                lines.append("")

    lines.extend(["## Source-quality and verification notes", ""])
    for note in SOURCE_NOTES:
        lines.append(f"- **{note['scope']} ({note['severity']}):** {note['note']}")
    lines.append("")
    return "\n".join(lines)


def html_document(markdown_text: str, chunks: list[dict[str, object]]) -> str:
    assignment_cards = []
    for assignment in ASSIGNMENTS:
        def list_html(values: list[str]) -> str:
            return "<ul>" + "".join(f"<li>{html.escape(value)}</li>" for value in values) + "</ul>"

        sections = [
            ("Learning objectives", assignment["objectives"]),
            ("Requirements", assignment["requirements"]),
        ]
        if assignment.get("architecture"):
            sections.append(("Architecture", assignment["architecture"]))
        if assignment.get("schema"):
            sections.append(("Database schema", assignment["schema"]))
        if assignment.get("crud_contracts"):
            sections.append(("CRUD contracts", assignment["crud_contracts"]))
        sections.extend(
            [
                ("Deliverables", assignment["deliverables"]),
                ("Rubric", assignment["rubric"]),
                ("Suggested Socratic prompts", assignment["socratic_prompts"]),
            ]
        )
        rendered_sections = "".join(
            f"<section><h3>{html.escape(title)}</h3>{list_html(values)}</section>"
            for title, values in sections
        )
        assignment_cards.append(
            f"""
            <article class="assignment" id="assignment-{assignment['number']}">
              <header><span class="eyebrow">Assignment {assignment['number']} · {assignment['points']} points</span>
              <h2>{html.escape(assignment['title'])}</h2></header>
              {rendered_sections}
            </article>
            """
        )

    note_html = "".join(
        f"<li><strong>{html.escape(note['scope'])}:</strong> {html.escape(note['note'])}</li>"
        for note in SOURCE_NOTES
    )
    course_policy_html = "".join(
        f"<section><h3>{html.escape(title)}</h3><ul>"
        + "".join(f"<li>{html.escape(value)}</li>" for value in COURSE_GUIDANCE[key])
        + "</ul></section>"
        for key, title in [
            ("topics", "Course coverage"),
            ("grading", "Grading"),
            ("late_policy", "Late policy"),
            ("ai_policy", "AI-use policy"),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{COURSE['course_name']} · {COURSE['term']} RAG Core</title>
  <style>
    :root {{ --ink:#172033; --muted:#5d687a; --paper:#f5f7fb; --card:#fff; --accent:#3157c8; --line:#dce2ef; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font:16px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    .wrap {{ width:min(1080px,calc(100% - 32px)); margin:auto; }}
    .hero {{ padding:64px 0 44px; color:#fff; background:linear-gradient(135deg,#17295f,#3157c8); }}
    .hero h1 {{ margin:.2rem 0; font-size:clamp(2rem,5vw,3.6rem); line-height:1.05; }}
    .hero p {{ max-width:760px; color:#e8edff; }}
    nav {{ position:sticky; top:0; z-index:2; padding:12px 0; background:rgba(245,247,251,.94); border-bottom:1px solid var(--line); backdrop-filter:blur(10px); }}
    nav a {{ display:inline-block; margin:4px 14px 4px 0; color:var(--accent); text-decoration:none; font-weight:650; }}
    main {{ padding:30px 0 64px; }}
    .callout,.assignment,.notes {{ margin:22px 0; padding:26px; background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:0 8px 28px rgba(28,43,82,.06); }}
    .callout {{ border-left:5px solid var(--accent); }}
    .assignment header {{ border-bottom:1px solid var(--line); margin-bottom:18px; }}
    h2 {{ font-size:1.65rem; line-height:1.2; }} h3 {{ margin:1.25rem 0 .3rem; font-size:1.02rem; color:#273969; }}
    .eyebrow {{ color:var(--accent); font-size:.82rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }}
    li {{ margin:.35rem 0; }} code {{ padding:.1rem .35rem; background:#edf1fa; border-radius:5px; }}
    footer {{ padding:28px 0; color:var(--muted); border-top:1px solid var(--line); }}
  </style>
</head>
<body>
  <header class="hero"><div class="wrap"><span class="eyebrow" style="color:#bccbff">RAG core documentation</span>
    <h1>{COURSE['course_name']}</h1><p>{COURSE['term']} · Socratic tutoring corpus for students and learners. Private personnel and meeting information is excluded.</p>
  </div></header>
  <nav><div class="wrap"><a href="#policy">Tutoring policy</a>{''.join(f'<a href="#assignment-{a["number"]}">A{a["number"]}</a>' for a in ASSIGNMENTS)}<a href="#notes">Source notes</a></div></nav>
  <main class="wrap">
    <section class="callout" id="policy"><h2>Socratic tutoring policy</h2><p>{html.escape(next(item['content'] for item in chunks if item['chunk_id'] == 'se3155-socratic-policy'))}</p></section>
    <section class="assignment"><header><span class="eyebrow">Course-level knowledge</span><h2>Course policies and coverage</h2></header>{course_policy_html}</section>
    {''.join(assignment_cards)}
    <section class="notes" id="notes"><h2>Source-quality notes</h2><ul>{note_html}</ul></section>
  </main>
  <footer><div class="wrap">Generated for {COURSE['course_name']} · {COURSE['term']} · {len(chunks)} retrieval chunks</div></footer>
</body>
</html>
"""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    chunks = build_chunks()
    markdown_text = markdown_document(chunks)

    (OUT_DIR / "software-engineering-3155-core.md").write_text(markdown_text, encoding="utf-8")
    # The current app ingests Markdown and applies fixed-size character chunking. Store each
    # semantic unit separately so unrelated assignments and rubric sections are not blended.
    for old_path in RAW_DOCS_DIR.glob("se3155-*.md"):
        old_path.unlink()
    for old_path in RAW_DOCS_DIR.glob("source-note-*.md"):
        old_path.unlink()
    legacy_combined = RAW_DOCS_DIR / "software-engineering-3155-fall-2026.md"
    if legacy_combined.exists():
        legacy_combined.unlink()
    for item in chunks:
        assignment_label = (
            f"Assignment {item['assignment_number']}: {item['assignment_title']}"
            if item.get("assignment_number")
            else "Course-wide"
        )
        runtime_text = "\n".join(
            [
                f"# {item['title']}",
                "",
                f"Course: {COURSE['course_name']}",
                f"Term: {COURSE['term']}",
                f"Scope: {assignment_label}",
                f"Content type: {item['content_type']}",
                f"Confidence: {item['confidence']}",
                "Keywords: " + ", ".join(str(value) for value in item["keywords"]),
                "",
                str(item["content"]),
                "",
            ]
        )
        (RAW_DOCS_DIR / f"{item['chunk_id']}.md").write_text(runtime_text, encoding="utf-8")
    (OUT_DIR / "software-engineering-3155-core.html").write_text(
        html_document(markdown_text, chunks), encoding="utf-8"
    )
    with (OUT_DIR / "software-engineering-3155-rag.jsonl").open("w", encoding="utf-8") as handle:
        for item in chunks:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    manifest = {
        **COURSE,
        "schema_version": "1.0",
        "generated_artifacts": [
            "software-engineering-3155-core.md",
            "software-engineering-3155-core.html",
            "software-engineering-3155-rag.jsonl",
        ],
        "runtime_ingestion_files": "backend/data/raw_docs/se3155-*.md",
        "chunk_count": len(chunks),
        "assignment_count": len(ASSIGNMENTS),
        "privacy_exclusions": [
            "Instructor and TA names and email addresses",
            "Private Zoom links",
            "Private collaboration identities",
            "Semester-specific deadlines not present in the supplied sources",
        ],
        "raw_source_handling": {
            "course_overview_pdf": "Preserved in backend/data/raw_docs and excluded through .ragignore after its non-private, instructionally relevant content was normalized into semantic chunks."
        },
        "retrieval_guidance": {
            "preferred_source": "software-engineering-3155-rag.jsonl",
            "current_app_compatible_source": "backend/data/raw_docs/se3155-*.md",
            "recommended_chunking": "Use the pre-authored JSONL records as semantic units; do not split function contracts, rubric totals, or source-quality notes across chunks.",
            "recommended_filters": ["course_id", "term", "assignment_number", "content_type", "confidence"],
        },
        "source_quality_notes": SOURCE_NOTES,
    }
    (OUT_DIR / "software-engineering-3155-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(json.dumps({"output_dir": str(OUT_DIR), "chunks": len(chunks)}, indent=2))


if __name__ == "__main__":
    main()
