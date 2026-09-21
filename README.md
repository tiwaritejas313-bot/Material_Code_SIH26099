# Material Harmonization Platform (SIH 26099)

This repository contains the **Material Harmonization Platform**, an intelligent enterprise system designed to normalize, match, and harmonize disparate legacy material descriptions across different entities. It utilizes modern AI (Sentence Transformers) to find equivalent materials, establish Common Material Groups, and maintain a robust review queue for human-in-the-loop validation.

## 🚀 Live Demo
- **Frontend (Vercel):** [https://material-code-sih-26099.vercel.app](https://material-code-sih-26099.vercel.app)
- **Backend API (Render):** [https://material-code-sih26099.onrender.com](https://material-code-sih26099.onrender.com)

---

## 🏗️ Architecture

The system is split into two primary components:

### 1. Frontend (`/frontend`)
A blazing-fast, responsive single-page application built with React and Vite. 
- **Framework:** React + Vite
- **Styling:** Vanilla CSS (Enterprise-grade UI with dynamic styling)
- **Routing:** React Router (Dashboard, Material Explorer, Review Queue, Legacy Mapping)
- **Deployment:** Vercel

### 2. Backend (`/backend`)
A high-performance Python API that handles data ingestion, NLP-based normalization, and semantic matching.
- **Framework:** FastAPI
- **Database:** MongoDB
- **AI/ML:** PyTorch + `sentence-transformers` (all-MiniLM-L6-v2) for semantic embedding generation and vector search.
- **Features:** 
  - Phase 1: Rule-based abbreviation and unit normalization
  - Phase 2: Attribute extraction
  - Phase 3: Semantic embedding retrieval
  - Phase 4: Deterministic compatibility evaluation
  - Phase 5: Human-in-the-loop Review Queue
- **Deployment:** Render (with PyTorch CPU-only optimizations for memory efficiency)

---

## 🛠️ Local Development Setup

### Prerequisites
- Node.js (v18+)
- Python (3.10+)
- MongoDB Atlas account (or local MongoDB instance)

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up Environment Variables:
   Create a `.env` file in the `backend/` directory with the following:
   ```ini
   MONGODB_URI=your_mongodb_connection_string
   MONGODB_DB_NAME=sih26099
   JWT_SECRET_KEY=your_secret_key
   CORS_ORIGINS=http://localhost:5173
   ```
5. Run the API Server:
   ```bash
   uvicorn app.main:app --port 8001 --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Set up Environment Variables:
   Create a `.env` file in the `frontend/` directory with the following:
   ```ini
   VITE_API_BASE_URL=http://localhost:8001
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`.

---

## 🔒 Authentication
Authentication logic has been streamlined for evaluation purposes. The application defaults to an `admin_auto` role with full access to the dashboard and review queues, bypassing the login screen for seamless reviewer access.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome. Feel free to check issues page if you want to contribute.

## 📝 License
This project was developed for the Smart India Hackathon (SIH).
