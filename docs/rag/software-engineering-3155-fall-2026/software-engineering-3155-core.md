---
course_id: software-engineering-3155-fall-2026
course_name: Software Engineering 3155
term: Fall 2026
document_type: rag_core_documentation
privacy: excludes_private_course_contacts
---

# Software Engineering 3155 — Fall 2026

## Purpose and tutoring policy

The chatbot supports students through Socratic questioning. It should first identify the student's current reasoning, then ask one focused question at a time. If the student is stuck, it should move through progressively stronger hints, a partial explanation, and only then a direct explanation. It should finish by asking the student to explain or apply the concept. For active graded work, it may clarify requirements, explain concepts, diagnose errors, review student-provided reasoning, and offer analogous examples. Course policy prohibits AI use for quizzes and prohibits generating coding-assignment code from scratch. Code-level help must be limited to debugging a learner's own attempt. The chatbot should not produce a complete ready-to-submit solution, fabricate missing assignment requirements, expose answer keys, or claim that an inferred detail is verified.

## Course learning path

Software Engineering 3155, Fall 2026, is represented in this corpus as a five-assignment learning sequence. Assignment 1 builds a procedural interactive Python sandwich-maker. Assignment 2 refactors it into modules and classes. Assignment 3 moves domain data into a MySQL relational database. Assignment 4 introduces FastAPI routes, HTTP parameters, request bodies, and interactive API documentation. Assignment 5 combines modular architecture, FastAPI, SQLAlchemy, MySQL, Pydantic schemas, and full CRUD endpoints.

## Course delivery and source authority

- The Fall 2026 course is asynchronous online.
- Canvas is the authoritative location for the current schedule, official assignment files, announcements, grades, and due dates.
- The cleaned RAG corpus intentionally excludes office hours, staff contact details, and meeting links.

## Course subject coverage

- Software engineering principles and the software development life cycle
- Software requirements and software design
- Agile development and Scrum
- Software testing and test-driven development
- Software implementation, security, deployment, and DevOps
- Object-oriented programming and version control
- Web development, APIs, databases, and full-stack development
- Containerization, Docker, cloud computing, and machine learning

## Module structure

- Preparation work may include installing tools, following guidelines, and completing surveys.
- Lecture material covers concepts, theory, and professional practices.
- Recitation material emphasizes practical tasks, assignment preparation, and discussion.
- Homework may include programming material, assignments, and quizzes.
- Additional resources may include cheat sheets, articles, new technologies, interview preparation, and extra credit.

## Development tools

- PyCharm
- MySQL Workbench
- Docker Desktop
- Git and GitHub
- Optional JetBrains tools such as WebStorm and DataGrip

## Grading

- Homework: 30%
- Quizzes: 20%
- Midterm: 15%
- Final project: 30%
- Attendance: 5%
- Letter grades: A=90–100%, B=80–89%, C=70–79%, D=60–69%, F=0–59%.

## Late policy

- The stated assignment late penalty is 5% per day.
- Assignments may be submitted up to one week late with a maximum stated penalty of 30%; after that point the stated result is zero credit.
- Quizzes do not allow late submission.
- Potential exceptions are handled case by case and require timely communication and appropriate justification through official course channels.

## AI-use policy

- Students may not use ChatGPT, GitHub Copilot, or similar AI tools for quizzes.
- Students may not use ChatGPT or similar AI tools to generate coding-assignment code from scratch.
- For coding assignments, students may use an AI chatbot to debug code they have written.
- This chatbot must therefore require the learner to provide their own attempt, reasoning, or error before offering code-level debugging guidance.

## Academic integrity

- Submitted work must be the student's own.
- External references used in reports must be cited.
- Duplicate or plagiarized work receives no credit and may lead to disciplinary action under the university academic-integrity code.

## Assignment 1: Interactive Ham Sandwich Maker Machine

**Points:** 50  
**Source status:** verified_from_pasted_canvas_content

### Learning objectives

- Build an interactive terminal program without hard-coding scenario outputs.
- Check whether sufficient ingredients exist before making a sandwich.
- Process coin input, validate payment, and calculate change.
- Update and report remaining resources.
- Use Git and conventional commit messages in a private GitHub repository.

### Prerequisites

- Basic Python
- Functions
- Dictionaries
- Loops and conditionals
- Git basics

### Requirements

- The user selects a sandwich size.
- The program checks available resources before production.
- If resources are insufficient, the program reports the shortage and does not make the sandwich.
- If resources are sufficient, the program accepts coins and compares the inserted amount with the cost.
- The program reports insufficient payment or returns the applicable change.
- The user can request a remaining-resource report and turn off the machine.
- Complete the supplied skeleton in PyCharm and submit main.py.

### Deliverables

- main.py
- Link to a private GitHub repository

### Version-control requirements

- Push with Git; manual file upload is not acceptable.
- Repository history must contain at least five commits.
- Commit messages must follow Conventional Commits.

### Rubric

- Program functionality: 8 points.
- check_resources: 8 points in the detailed rubric.
- process_coins: 8 points in the detailed rubric.
- transaction_result: 8 points in the detailed rubric.
- make_sandwich: 8 points in the detailed rubric.
- GitHub repository and version-control requirements: 10 points.

### Suggested Socratic prompts

- What information must be known before the machine can decide whether to make a sandwich?
- What should remain unchanged when either resources or payment are insufficient?
- What single responsibility does each required function have?
- Which test case would reveal that a resource was deducted too early?

### Required function contracts

- `check_resources(ingredients: dict) -> bool` — Determine whether the machine has enough of every required ingredient.
- `process_coins() -> float` — Collect coin quantities and return the total monetary value inserted.
- `transaction_result(coins: float, cost: float) -> bool` — Determine whether payment succeeds and handle insufficient funds or change.
- `make_sandwich(sandwich_size: str, ingredients: dict) -> None` — Deduct required ingredients and complete the selected sandwich.

## Assignment 2: Modular Ham Sandwich Maker Machine

**Points:** 30  
**Source status:** verified_from_pasted_canvas_content

### Learning objectives

- Refactor the Assignment 1 program into modules and classes.
- Separate production, payment, data, and application-control responsibilities.
- Preserve the observable behavior of the Assignment 1 scenario.

### Prerequisites

- Assignment 1
- Python modules
- Classes and objects
- Imports

### Requirements

- Use four files: main.py, data.py, sandwich_maker.py, and cashier.py.
- Import data, sandwich_maker, and cashier at the top of main.py.
- Create variables from the resources and recipes dictionaries in data.py.
- Create instances of SandwichMaker and Cashier; SandwichMaker receives resources through its constructor.
- Move check_resources and make_sandwich into SandwichMaker.
- Move process_coins and transaction_result into Cashier.
- Keep recipes and resources in data.py as temporary in-memory data.
- Use main.py as the program entry point and integration layer.

### Architecture

- data.py: stores resources and recipes data.
- sandwich_maker.py: defines SandwichMaker and all sandwich-production behavior.
- cashier.py: defines Cashier and all payment behavior.
- main.py: creates objects, receives user commands, and coordinates the modules.

### Deliverables

- GitHub repository link; do not submit a ZIP file

### Version-control requirements

- Commit and push all assignment files to GitHub.

### Rubric

- Module implementation: 6 points.
- Code skeleton utilization: 6 points.
- Class and function migration: 6 points.
- Program functionality and integration: 6 points.
- Code quality and conventions: 6 points.

### Suggested Socratic prompts

- Which responsibilities in Assignment 1 naturally belong together?
- Which object needs access to resources, and why should that dependency be passed to its constructor?
- What should main.py coordinate without implementing itself?
- How can you verify that refactoring changed structure but not behavior?

## Assignment 3: Sandwich Maker Database

**Points:** 50  
**Source status:** verified_from_pasted_canvas_content

### Learning objectives

- Create a MySQL database for the Sandwich Maker domain.
- Represent resources, sandwich prices, and recipes as relational tables.
- Insert supplied seed data and verify it with SELECT queries.

### Prerequisites

- Assignments 1 and 2
- Basic SQL
- MySQL
- Relational tables

### Requirements

- Install MySQL and MySQL Workbench.
- Create a database using an explicit database-creation statement.
- Create resources, sandwiches, and recipes tables using the required columns and types.
- Insert all supplied seed data.
- Execute a SELECT statement for each table and capture its result.

### Database schema

- resources(item VARCHAR(50), amount INT)
- sandwiches(sandwich_size VARCHAR(50), price DECIMAL(5,2))
- recipes(sandwich_size VARCHAR(50), item VARCHAR(50), amount INT)

### Deliverables

- One .sql file containing all database, CREATE TABLE, INSERT, and SELECT statements.
- Three screenshots: one SELECT result for each table.

### Rubric

- Database creation statement: 2 points.
- Three CREATE TABLE statements: 15 points.
- Three groups of INSERT statements: 18 points.
- Three SELECT statements: 3 points.
- Three table-result screenshots: 12 points.

### Suggested Socratic prompts

- Which facts describe inventory, which describe products, and which connect products to ingredients?
- Why does one sandwich size require several rows in recipes?
- Which SQL query would prove that every required seed row was inserted?
- What data problem could occur if size names use inconsistent capitalization?

### Required seed data

#### resources

- item=bread, amount=12
- item=ham, amount=18
- item=cheese, amount=24

#### sandwiches

- sandwich_size=small, price=1.75
- sandwich_size=medium, price=3.25
- sandwich_size=large, price=5.5

#### recipes

- sandwich_size=small, item=bread, amount=2
- sandwich_size=small, item=ham, amount=4
- sandwich_size=small, item=cheese, amount=4
- sandwich_size=medium, item=bread, amount=4
- sandwich_size=medium, item=ham, amount=6
- sandwich_size=medium, item=cheese, amount=8
- sandwich_size=large, item=bread, amount=6
- sandwich_size=large, item=ham, amount=8
- sandwich_size=large, item=cheese, amount=12

## Assignment 4: FastAPI Implementation

**Points:** 15  
**Source status:** partially_verified_missing_source_code_blocks

### Learning objectives

- Create and run a simple FastAPI application.
- Understand routes, HTTP GET and PUT methods, path parameters, query parameters, and request bodies.
- Use Pydantic-compatible Python types for a request body.
- Use FastAPI's generated interactive API documentation to exercise endpoints.

### Prerequisites

- Python functions
- HTTP basics
- Virtual environments

### Requirements

- Install fastapi and uvicorn[standard] in the project virtual environment.
- Create main.py containing the assignment's FastAPI application code; the pasted source does not include that code block.
- Run the application with: uvicorn main:app --reload.
- Provide GET routes at / and /items/{item_id}.
- The item_id path parameter must be an integer.
- The /items/{item_id} route accepts an optional string query parameter named q.
- Add a request-body model and a PUT route as directed by the original assignment; the pasted source omits the model and route code.
- Use http://127.0.0.1:8000/docs and run every required request.

### Verification

- For Part 1, capture one screenshot for each GET endpoint, including parameters and response body.
- For Part 2, execute the PUT request through interactive API docs and capture the required result.
- Run all requests required by both parts.

### Deliverables

- GitHub repository containing complete source code and main.py in the assignment folder.
- Screenshots from the interactive API docs for the required requests.

### Version-control requirements

- At least three commits are required.
- Commit messages must follow Conventional Commits.
- The final commit must precede the assignment submission time.
- A source instruction says to invite the course TAs as collaborators; identifying information is excluded from this corpus.

### Rubric

- main.py correctness: 5 points.
- Required screenshots and experimentation: 7 points.
- GitHub submission: 3 points.

### Suggested Socratic prompts

- Which part of the URL identifies the resource, and which part supplies an optional value?
- Why must item_id be declared as an integer?
- What changes between a GET request and a PUT request with a body?
- What evidence in the interactive documentation demonstrates that an endpoint works?

## Assignment 5: CRUD Operations in FastAPI

**Points:** 80  
**Source status:** verified_from_assignment_page_7_and_pasted_canvas_content

### Learning objectives

- Build a modular database-backed FastAPI application.
- Connect FastAPI to a MySQL database using SQLAlchemy and PyMySQL.
- Implement Create, Read, Update, and Delete operations for required domain tables.
- Separate controllers, persistence models, API schemas, dependencies, and routes.

### Prerequisites

- Assignments 2 through 4
- FastAPI
- SQLAlchemy
- MySQL
- Pydantic schemas
- REST CRUD

### Setup

- Start from the code base supplied on the assignment page.
- Install fastapi, uvicorn[standard], sqlalchemy, and pymysql in the virtual environment.
- Create a MySQL database named sandwich_maker_api.
- Configure the database name, MySQL username, and password in api/dependencies/config.py.
- From the assignment directory run: uvicorn api.main:app --reload.
- On startup, SQLAlchemy should create five tables: sandwiches, resources, recipes, orders, and order_details.

### Requirements

- Use the supplied orders controller and routes as the implementation pattern.
- Create controller modules for sandwiches, resources, recipes, and order_details.
- For each required table implement create, read_all, read_one, update, and delete.
- Add corresponding POST, GET collection, GET item, PUT, and DELETE endpoints in api/main.py.
- Use paths, parameter names, schema types, response models, and tags appropriate to each table.
- Return 404 when a requested record does not exist.
- Verify every endpoint using http://127.0.0.1:8000/docs.

### Architecture

- api/controllers/: one controller module per table; controller functions perform database CRUD operations.
- api/models/models.py: SQLAlchemy classes describing database tables and relationships.
- api/models/schemas.py: request and response schemas used by the API.
- api/dependencies/config.py: database and project configuration values.
- api/dependencies/database.py: database engine, session, and connection handling.
- api/main.py: FastAPI entry point and route definitions that delegate work to controllers.

### CRUD contracts

- create: instantiate the SQLAlchemy model, add it to the session, commit, refresh, and return it.
- read_all: query the table and return all rows.
- read_one: filter by the record identifier and return the first match or None.
- update: locate the record, apply only supplied fields, commit, and return the updated row.
- delete: locate and delete the record, commit, and return HTTP 204 No Content.

### Deliverables

- GitHub repository containing complete source code in the assignment folder

### Version-control requirements

- Commit and push the work; manual upload is not an equivalent substitute.
- Commit messages must follow Conventional Commits.
- The final commit must precede the assignment submission time.

### Rubric

- Table/schema implementation for sandwiches, resources, recipes, and order_details: 8 points each (32 total).
- CRUD endpoint implementation for sandwiches, resources, recipes, and order_details: 10 points each (40 total).
- Repository submission and pushed source code: 8 points.

### Suggested Socratic prompts

- Which layer should know SQLAlchemy, and which layer should know HTTP routes?
- How can the supplied orders implementation serve as a pattern without copying table-specific names incorrectly?
- What should read_one return when the database contains no matching row, and which layer converts that into HTTP 404?
- Why should an update schema distinguish omitted fields from fields explicitly set by the client?
- Which sequence of API requests would verify a complete CRUD lifecycle?

## Source-quality and verification notes

- **Assignment 4 (high):** The pasted Assignment 4 page omits the example Python code blocks and several example responses/images. The corpus states the observable endpoint requirements but does not invent the missing code. Obtain the original linked assignment document before using the chatbot for line-by-line implementation guidance.
- **Assignment 4 (medium):** One sentence says Flask, while the title, package installation, Uvicorn command, interactive documentation, and remaining instructions consistently specify FastAPI. The corpus treats FastAPI as authoritative and records Flask as a likely source typo.
- **Assignment 1 (medium):** The compact Part 1 function table assigns 4 points per function, but the detailed Canvas rubric assigns 8 points per function. The detailed rubric totals the stated 40 Part 1 points and is therefore used as the authoritative scoring interpretation.
- **Assignment 2 (low):** The filename sandwich_makerr.py appears once with a doubled r. The surrounding instructions refer to the sandwich_maker module. The corpus uses sandwich_maker.py and flags the original spelling for instructor verification.
- **Assignment 5 (medium):** The assignment says SQLAlchemy creates five tables and later names sandwiches, resources, recipes, orders, and order_details. The task text says the orders implementation is supplied as the example and students implement the other four controllers and endpoint groups.
- **All assignments (medium):** Deadlines, semester-specific Canvas identifiers, private repository invitations, instructor and TA contact details, and private meeting links are intentionally excluded from this learner corpus.
