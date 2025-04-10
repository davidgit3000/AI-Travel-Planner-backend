# AI Travel Planner (backend)

A FastAPI-based backend service for the AI Travel Planner application that helps users create personalized travel itineraries.

## Features

- User authentication and authorization
- Travel itinerary generation
- Database integration for user data and travel plans
- RESTful API endpoints

## Tech Stack

- Python 3.x
- FastAPI
- PostgreSQL
- JWT Authentication

## Project Structure

```
├── auth/           # Authentication related modules
├── models/         # Database models
├── routes/         # API route handlers
├── database.py     # Database configuration
├── main.py         # Application entry point
└── requirements.txt
```

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables in `.env` file

4. Run the application:
   ```bash
   python -m uvicorn main:app --reload
   ```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## License

MIT License
