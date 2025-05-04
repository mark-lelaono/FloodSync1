# FloodSync

A flood mapping application using Google Earth Engine (backend) and Shiny (frontend).

## Setup

### Backend
1. Create a virtual environment:
   ```bash
   python -m venv floodsync_env
   .\floodsync_env\Scripts\activate
   pip install geemap fastapi uvicorn setuptools
   
