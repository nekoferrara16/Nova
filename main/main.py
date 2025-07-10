
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi import Request
from fastapi.templating import Jinja2Templates
import random 
from charts.networthchart import networth # Importing the networth chart function from charts/networthchart.py
from charts.networthchart import expense_chart # Importing the expense chart function from charts/networthchart.py
# from charts.networthchart import income_chart # Importing the income chart function from charts/networthchart.py
from charts.networthchart import credit_card_balances
from charts.networthchart import income_chart # Importing the income chart function from charts/networthchart.py


#Main dashboard and functions are located in this file 
app = FastAPI() 

templates = Jinja2Templates(directory="../templates") #templates directory for HTML files
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request): 
    #sample data for the dashboard 
    # This data is for demonstration purposes and should be replaced with actual data from your application.
    
    monthly_income = [6085]  # Example
    categories = ["Housing", "Food", "Transportation", "Entertainment", "Healthcare", "Utilities", "Clothing", "Education", "Car Payment" "Miscellaneous"]
    category_amounts = [1370, 300, 200, 150, 100, 80, 70, 50, 545.90, 30]  # Example amounts for each category
    
    category_amount_sum = sum(category_amounts)  # Calculate the total amount for all categories
    
    dates = ["2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01", "2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01"]
    values = [10000]
    credit_cards = {
    "Chase Sapphire": 1250.50,
    "Discover It": 920.15,
    "Citi Double Cash": 1643.75,
    "Amex Blue": 875.30,
    "Capital One": 1120.00
}
    
    #random number generator for networth values to test chart 
    for _ in range(len(dates)):
        values.append(values[-1] + random.randint(-1000, 200000))

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "dates": dates,
        "values": values,
        "net_worth_chart": networth(dates, values),  # Call the networth function to get the chart HTML
        "expense_chart": expense_chart(categories, category_amounts),  # Call the expense chart function to get the chart HTML    
        "credit_card_balances": credit_card_balances(credit_cards),  # Call the credit card balances function to get the chart HTML
        "income_chart": income_chart(monthly_income, category_amount_sum)  # Call the income chart function to get the chart HTML
    })


