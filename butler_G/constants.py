"""Constants

Note: NOTHING should be imported here
"""

WARN_THRESH = 0.8

# Responses
YES = "Yes"
NO = "No"

# Global States
TASK = "TASK"

# Expense Log States
EXPENSE_CATEGORY = "EXPENSE_CATEGORY"
EXPENSE_CATEGORY2 = "EXPENSE_CATEGORY2"
EXPENSE_AMOUNT = "EXPENSE_AMOUNT"
EXPENSE_NOTES = "EXPENSE_NOTES"
UPLOAD_EXPENSE = "UPLOAD_EXPENSE"
REVIEW_EXPENSE_UPLOAD = "REVIEW_EXPENSE_UPLOAD"
PROCESS_EXP_UPLOAD_REVIEW = "PROCESS_EXP_UPLOAD_REVIEW"
GET_TXNS = "GET_TXNS"

# Tasks
LOG_EXPENSE = "Log Expense"
SPEND_MONTH = "Show Spend for the Month"
LAST_TXNS = "Show Last Transactions"

TASKS = (LOG_EXPENSE, SPEND_MONTH, LAST_TXNS)

# Expense Categories
EXPENSE_CATEGORIES = (
    "Quick Meal",
    "Dining & Ent",
    "Groceries & HH",
    "Transportation",
    "Shopping",
    "Rent",
    "Utilities",
    "Other",
)

# Flavor lines
EXIT_STR = "Nah G, is cool. Carry on"

LINES_SHAME = (
    "Well, someone got a bit carried away.",
    "I hope you have a good explanation for this.",
    "Look at Master Moneybags over here.",
    "Quite a prudent expenditure, might I say.",
    "What an excellent use of financial resources.",
    "There goes junior's college fund.",
)
