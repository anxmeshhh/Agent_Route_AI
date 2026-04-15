"""
run.py — Entry point for the ShipRiskAI application
Usage: python run.py
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    print("""
======================================================================
    ShipRiskAI — Predictive Delay & Risk Intelligence (AGENTIC)       
    8-Agent Graph  |  LLM Router  |  Cross-Validation  |  Memory      
======================================================================
    Dashboard:  http://127.0.0.1:5000                                 
    Health:     http://127.0.0.1:5000/health                          
    Analyze:    POST http://127.0.0.1:5000/api/analyze                
    Tools:      GET  http://127.0.0.1:5000/api/tools                  
    Analytics:  GET  http://127.0.0.1:5000/api/analytics              
======================================================================
    """)
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=app.config.get("DEBUG", True),
        threaded=True,   # Required for SSE concurrent connections
        use_reloader=True,
    )
