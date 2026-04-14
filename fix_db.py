from app import create_app
from app.database import execute_query

app = create_app()

with app.app_context():
    execute_query("DROP TABLE IF EXISTS agent_logs;")
    execute_query("DROP TABLE IF EXISTS prediction_outcomes;")
    execute_query("DROP TABLE IF EXISTS analysis_memory;")
    execute_query("DROP TABLE IF EXISTS risk_assessments;")
    
    print("Dropped tables. Running init_schema...")
    from app.database import init_schema
    init_schema(app)
    print("Database schema successfully recreated!")
