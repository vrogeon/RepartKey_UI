#!/usr/bin/env python3
# cleanup_cookies.py - Nettoyage des consentements expirés

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_auth import app
from cookies_consent import cleanup_old_consents

with app.app_context():
    deleted = cleanup_old_consents()
    print(f"✅ {deleted} consentements expirés supprimés")
