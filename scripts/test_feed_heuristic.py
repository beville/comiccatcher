import asyncio
import sys
import os
import argparse

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.client import APIClient
from api.opds_v2 import OPDS2Client
from api.feed_reconciler import FeedReconciler
from models.feed import FeedProfile
from ui.theme_manager import UIConstants

async def test_url(url, token=None):
    print(f"🧪 Testing URL: {url}")
    if token:
        print(f"🔑 Using Bearer Token: {token[:10]}...")
    
    # Setup minimal environment
    UIConstants.LARGE_SECTION_THRESHOLD = 200 
    
    profile = FeedProfile(id="test", name="Test", url=url, bearer_token=token)
    api_client = APIClient(profile)
    opds_client = OPDS2Client(api_client)
    
    try:
        print("📡 Fetching feed...")
        feed = await opds_client.get_feed(url)
        
        print("🔄 Reconciling...")
        page = FeedReconciler.reconcile(feed, url)
        
        print(f"\n--- Result for '{page.title}' ---")
        print(f"Is Dashboard: {page.is_dashboard}")
        
        main = page.main_section
        print(f"Main Section: {main.title if main else 'None (All Ribbons)'}")
        
        print("\nSections:")
        for s in page.sections:
            is_main = (main and s.section_id == main.section_id)
            has_link = bool(s.self_url)
            has_next = bool(s.next_url)
            count = len(s.items)
            print(f"  - {s.title:25} | items={count:3} | main={str(is_main):5} | has_link={str(has_link):5} | has_next={str(has_next):5}")

        if page.is_dashboard:
            if main is None:
                print("\n✅ Dashboard: All sections are preview ribbons.")
            else:
                print(f"\nℹ️ Dashboard: Section '{main.title}' promoted to Main Grid (likely large or paginated).")
        else:
            print("\n📄 List View: All sections will render as Grids.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await api_client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test feed layout heuristics.")
    parser.add_argument("url", help="The OPDS 2.0 URL to test")
    parser.add_argument("-t", "--token", help="Bearer token for authentication", default=None)
    args = parser.parse_args()
    
    asyncio.run(test_url(args.url, args.token))
