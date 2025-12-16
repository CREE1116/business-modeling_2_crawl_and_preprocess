import sys
from unittest.mock import MagicMock
import pandas as pd
import os
import glob

# Mock undetected_chromedriver and selenium before importing the module
sys.modules["undetected_chromedriver"] = MagicMock()
sys.modules["selenium"] = MagicMock()
sys.modules["selenium.webdriver"] = MagicMock()
sys.modules["selenium.webdriver.common"] = MagicMock()
sys.modules["selenium.webdriver.common.by"] = MagicMock()
sys.modules["selenium.webdriver.support"] = MagicMock()
sys.modules["selenium.webdriver.support.ui"] = MagicMock()
sys.modules["selenium.webdriver.support.expected_conditions"] = MagicMock()

# Add the directory to sys.path so we can import the module
sys.path.append(os.getcwd())

import youtube_tech_trend_pipeline.twitter_follower_crawler as crawler

def test_crawler_logic():
    print("Starting verification test...")
    
    # Setup dummy data
    os.makedirs("data/twitter", exist_ok=True)
    dummy_file = "data/twitter/twitter_merged_test_9999.csv"
    
    # Create dummy CSV with one user having existing count and one without
    df = pd.DataFrame({
        'author_id': ['@test_new', '@test_existing'],
        'follower_count': [-1, 500] # -1 means needs update, 500 means already done
    })
    df.to_csv(dummy_file, index=False)
    print(f"Created dummy file: {dummy_file}")
    
    # Mock driver behavior
    mock_driver = MagicMock()
    # Mock init_driver to return our mock driver
    crawler.init_driver = MagicMock(return_value=mock_driver)
    
    # Mock get_latest_input_file to return our dummy file
    crawler.get_latest_input_file = MagicMock(return_value=dummy_file)
    
    # Mock get_follower_count to return a value
    # It should be called only for @test_new
    # We'll make it return 12345
    crawler.get_follower_count = MagicMock(return_value=12345)
    
    try:
        # Run main
        crawler.main()
        
        # Verify
        df_new = pd.read_csv(dummy_file)
        print("\nUpdated DataFrame:")
        print(df_new)
        
        # Check test_new
        new_count = df_new.loc[df_new['author_id'] == '@test_new', 'follower_count'].values[0]
        if new_count == 12345:
            print("\n[PASS] @test_new updated correctly.")
        else:
            print(f"\n[FAIL] @test_new has {new_count}, expected 12345.")
            
        # Check test_existing
        existing_count = df_new.loc[df_new['author_id'] == '@test_existing', 'follower_count'].values[0]
        if existing_count == 500:
            print("[PASS] @test_existing preserved correctly.")
        else:
            print(f"[FAIL] @test_existing has {existing_count}, expected 500.")
            
        # Check if author_id_clean was removed
        if 'author_id_clean' not in df_new.columns:
            print("[PASS] Temporary column 'author_id_clean' removed.")
        else:
            print("[FAIL] Temporary column 'author_id_clean' still exists.")

    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
    finally:
        # Cleanup
        if os.path.exists(dummy_file):
            os.remove(dummy_file)
            print(f"\nCleaned up {dummy_file}")

if __name__ == "__main__":
    test_crawler_logic()
