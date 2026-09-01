# Assignment 5 required architecture

Course: Software Engineering 3155
Term: Fall 2026
Scope: Assignment 5: CRUD Operations in FastAPI
Content type: software_architecture
Confidence: verified
Keywords: architecture, structure, contract

Required architecture: 1) api/controllers/: one controller module per table; controller functions perform database CRUD operations. 2) api/models/models.py: SQLAlchemy classes describing database tables and relationships. 3) api/models/schemas.py: request and response schemas used by the API. 4) api/dependencies/config.py: database and project configuration values. 5) api/dependencies/database.py: database engine, session, and connection handling. 6) api/main.py: FastAPI entry point and route definitions that delegate work to controllers.
