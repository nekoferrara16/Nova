#charts for the application - need to integrate with the rest of the app, specifically plaid. 

# charts/charts.py using plotly 

from plotly import graph_objects as go 

#creating a networth chart 

def networth(dates, values): 
    figure = go.Figure(data=go.Scatter(x=dates, y=values, mode='lines+markers'))
    figure.update_layout(
        title='Net Worth Over Time',
        xaxis_title='Date',
        yaxis_title='Net Worth ($)',
        template='plotly_dark'
    )
    return figure.to_html(full_html=False)

def expense_chart(categories, amounts):
    figure = go.Figure(data=go.Pie(labels=categories, values=amounts))
    figure.update_layout(
        title='Expense Distribution by Category',
        template='plotly_dark'
    )
    return figure.to_html(full_html=False)

def credit_card_balances(cards: dict):
    fig = go.Figure([go.Bar(
        x=list(cards.keys()),
        y=list(cards.values()),
        marker_color='crimson'
    )])

    fig.update_layout(
        title="Credit Card Balances",
        xaxis_title="Credit Card",
        yaxis_title="Balance ($)",
        template="plotly_dark"
    )

    return fig.to_html(full_html=False)

#cashflow 

def income_chart(income, categroy_amount_sum):
    figure = go.Figure(data=go.Bar(x=["Income", "Expenses"], y=[sum(income), categroy_amount_sum]))
    figure.update_layout(
        title='Income vs Expenses',
        xaxis_title='Category',
        yaxis_title='Amount ($)',
        template='plotly_dark'
    )
    return figure.to_html(full_html=False)