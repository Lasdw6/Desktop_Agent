#!/usr/bin/env python
"""
Simple Chrome automation test
Opens Chrome and tests element discovery
"""

import json
import sys
import time
import subprocess
import webbrowser

# Add src-py to path
sys.path.append('src-py')

from web_browser_automation import WebBrowserAutomation, find_web_element_by_description

def open_chrome_with_url(url="https://www.google.com"):
    """Open Chrome with a specific URL"""
    try:
        # Try to open Chrome specifically
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        subprocess.Popen([chrome_path, url])
        print(f"✅ Opened Chrome with {url}")
        return True
    except Exception as e:
        print(f"❌ Failed to open Chrome: {e}")
        try:
            # Fallback to default browser
            webbrowser.open(url)
            print(f"✅ Opened default browser with {url}")
            return True
        except Exception as e2:
            print(f"❌ Failed to open any browser: {e2}")
            return False

def test_chrome_automation():
    """Test Chrome automation with a real browser window"""
    print("🌐 CHROME AUTOMATION TEST")
    print("=" * 50)
    
    # Step 1: Open Chrome
    print("\n1. Opening Chrome...")
    if not open_chrome_with_url("https://www.google.com"):
        print("❌ Could not open Chrome. Test aborted.")
        return
    
    # Wait for Chrome to load
    print("⏳ Waiting 3 seconds for Chrome to load...")
    time.sleep(3)
    
    # Step 2: Discover Chrome elements
    print("\n2. Discovering Chrome elements...")
    browser_automation = WebBrowserAutomation()
    
    # Test all browsers first
    all_elements = browser_automation.discover_browser_elements()
    print(f"📊 All browsers found: {all_elements.get('total_elements', 0)} elements")
    
    if all_elements.get('browser_windows'):
        print("🖥️ Browser windows found:")
        for window in all_elements['browser_windows']:
            print(f"   • {window['name']} ({window['class_name']})")
    
    # Test Chrome specifically
    chrome_elements = browser_automation.discover_browser_elements('chrome')
    print(f"\n🎯 Chrome-specific discovery: {chrome_elements.get('total_elements', 0)} elements")
    
    if isinstance(chrome_elements, dict) and 'error' not in chrome_elements:
        print("✅ Chrome elements found:")
        print(f"   • Browser windows: {len(chrome_elements.get('browser_windows', []))}")
        print(f"   • Tabs: {len(chrome_elements.get('tabs', []))}")
        print(f"   • Address bars: {len(chrome_elements.get('address_bars', []))}")
        print(f"   • Navigation buttons: {len(chrome_elements.get('navigation_buttons', []))}")
        print(f"   • Clickable elements: {chrome_elements.get('clickable_count', 0)}")
        print(f"   • Typable elements: {chrome_elements.get('typable_count', 0)}")
        
        # Show some clickable elements
        if chrome_elements.get('clickable_elements'):
            print("\n🖱️ Sample clickable elements:")
            for elem in chrome_elements['clickable_elements'][:5]:
                print(f"   • {elem['description']}")
        
        # Test element search
        print("\n🔍 Testing element search...")
        search_terms = ["address", "back", "refresh", "tab"]
        for term in search_terms:
            found = find_web_element_by_description(term, chrome_elements)
            if found:
                print(f"✅ Found '{term}': {found['description']}")
            else:
                print(f"❌ '{term}' not found")
        
        # Save results
        with open('chrome_test_results.json', 'w') as f:
            json.dump(chrome_elements, f, indent=2)
        print("\n💾 Results saved to 'chrome_test_results.json'")
        
    else:
        print(f"❌ Chrome discovery failed: {chrome_elements}")
    
    print("\n🎉 Chrome automation test completed!")

if __name__ == "__main__":
    test_chrome_automation() 