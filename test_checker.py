import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app
from app.checker import check_single_cookie, CHECKER_AVAILABLE

print("CHECKER_AVAILABLE:", CHECKER_AVAILABLE)

app = create_app()

with app.app_context():
    # just dummy check
    res = check_single_cookie("dummy_cookie")
    print("Result:", res)
