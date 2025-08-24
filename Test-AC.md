1. Install Required Services:
  # PostgreSQL
  brew install postgresql@14  # macOS
  sudo apt-get install postgresql-14  # Ubuntu

  # Redis
  brew install redis  # macOS
  sudo apt-get install redis-server  # Ubuntu
  2. Start Services:
  # PostgreSQL
  brew services start postgresql@14  # macOS
  sudo systemctl start postgresql  # Ubuntu

  # Redis
  brew services start redis  # macOS
  sudo systemctl start redis  # Ubuntu
  3. Create Database:
  createdb auraconnect

  Method 1: Quick Start (All Services)

  1. Make scripts executable:
  chmod +x start-all.sh quick-setup.sh
  chmod +x backend/start-backend.sh frontend/start-frontend.sh
  2. Run quick setup (first time only):
  ./quick-setup.sh
  3. Start all services:
  ./start-all.sh

  This will open separate terminal windows for each service.

  Method 2: Manual Start (Step by Step)

  Backend:

  cd backend
  source venv/bin/activate
  pip install -r requirements.txt
  pip install psutil==5.9.8 twilio  # Additional packages

  # Copy and configure environment
  cp .env.example .env
  # Edit .env with your settings

  # Run migrations
  alembic upgrade head

  # Start backend
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

  Frontend:

  cd frontend
  npm install

  # Create .env
  echo "REACT_APP_API_URL=http://localhost:8000" > .env

  # Start frontend
  npm start

  Mobile (Optional):

  cd mobile
  npm install

  # iOS only
  cd ios && pod install && cd ..

  # Start Metro bundler
  npx react-native start

  # In another terminal:
  npx react-native run-ios  # or run-android

  Method 3: Using Individual Startup Scripts

  # Terminal 1 - Backend
  cd backend
  ./start-backend.sh

  # Terminal 2 - Frontend
  cd frontend
  ./start-frontend.sh

  Service URLs

  Once started, access the services at:
  - Frontend: http://localhost:3000
  - Backend API: http://localhost:8000
  - API Documentation: http://localhost:8000/docs
  - ReDoc: http://localhost:8000/redoc
  - Health Check: http://localhost:8000/health

  Test Credentials

  - Admin: username=admin, password=secret
  - Manager: username=manager, password=secret
  - Payroll: username=payroll_clerk, password=secret

  Troubleshooting

  1. Port already in use:
  # Kill process on port 8000
  lsof -ti:8000 | xargs kill -9

  # Kill process on port 3000
  lsof -ti:3000 | xargs kill -9
  2. Database connection errors:
    - Check PostgreSQL is running: pg_isready
    - Verify DATABASE_URL in .env
  3. Redis connection errors:
    - Check Redis is running: redis-cli ping
    - Verify REDIS_URL in .env
  4. Import errors:
    - Ensure virtual environment is activated
    - Reinstall dependencies: pip install -r requirements.txt

  The startup scripts include health checks and will provide clear error messages if any service fails to start.
