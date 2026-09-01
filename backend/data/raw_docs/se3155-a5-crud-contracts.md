# Assignment 5 crud operation contracts

Course: Software Engineering 3155
Term: Fall 2026
Scope: Assignment 5: CRUD Operations in FastAPI
Content type: crud_contracts
Confidence: verified
Keywords: crud contracts, structure, contract

CRUD operation contracts: 1) create: instantiate the SQLAlchemy model, add it to the session, commit, refresh, and return it. 2) read_all: query the table and return all rows. 3) read_one: filter by the record identifier and return the first match or None. 4) update: locate the record, apply only supplied fields, commit, and return the updated row. 5) delete: locate and delete the record, commit, and return HTTP 204 No Content.
