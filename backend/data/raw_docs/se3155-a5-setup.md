# Assignment 5 setup and execution

Course: Software Engineering 3155
Term: Fall 2026
Scope: Assignment 5: CRUD Operations in FastAPI
Content type: setup_instructions
Confidence: verified
Keywords: install, run, database, uvicorn, configuration

Required setup: 1) Start from the code base supplied on the assignment page. 2) Install fastapi, uvicorn[standard], sqlalchemy, and pymysql in the virtual environment. 3) Create a MySQL database named sandwich_maker_api. 4) Configure the database name, MySQL username, and password in api/dependencies/config.py. 5) From the assignment directory run: uvicorn api.main:app --reload. 6) On startup, SQLAlchemy should create five tables: sandwiches, resources, recipes, orders, and order_details.
