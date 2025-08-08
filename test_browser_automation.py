#!/usr/bin/env python
"""
Test script for Web Browser Automation

This script demonstrates the capabilities of the web browser automation system.
"""

import json
import sys
import os

# Add src-py to path to import our modules
sys.path.append('src-py')

from web_browser_automation import WebBrowserAutomation, find_web_element_by_description

def test_browser_discovery():
    """Test browser window discovery"""
    print("🔍 Testing Browser Discovery...")
    print("=" * 50)
    
    browser_automation = WebBrowserAutomation()
    
    # Test 1: Discover all browser elements
    print("\n1. Discovering all browser elements...")
    elements = browser_automation.discover_browser_elements()
    
    if 'error' in elements:
        print(f"❌ Error: {elements['error']}")
        return False
    
    print(f"✅ Found {elements['total_elements']} total elements")
    print(f"   • Browser windows: {len(elements.get('browser_windows', []))}")
    print(f"   • Tabs: {elements.get('tabs_count', 0)}")
    print(f"   • Address bars: {len(elements.get('address_bars', []))}")
    print(f"   • Navigation buttons: {len(elements.get('navigation_buttons', []))}")
    print(f"   • Web content: {elements.get('web_content_count', 0)}")
    print(f"   • Clickable elements: {elements.get('clickable_count', 0)}")
    print(f"   • Typable elements: {elements.get('typable_count', 0)}")
    
    return elements

def test_chrome_specific():
    """Test Chrome-specific discovery"""
    print("\n🌐 Testing Chrome-Specific Discovery...")
    print("=" * 50)
    
    browser_automation = WebBrowserAutomation()
    elements = browser_automation.discover_browser_elements('chrome')
    
    if 'error' in elements:
        print(f"❌ Chrome not found: {elements['error']}")
        return None
    
    print(f"✅ Chrome discovery successful!")
    print(f"   • Total Chrome elements: {elements['total_elements']}")
    
    # Show Chrome-specific elements
    if elements.get('browser_windows'):
        print(f"   • Chrome windows:")
        for window in elements['browser_windows']:
            print(f"     - {window['name']}")
    
    return elements

def test_element_search(elements):
    """Test searching for specific elements"""
    print("\n🎯 Testing Element Search...")
    print("=" * 50)
    
    if not elements or 'error' in elements:
        print("❌ No elements to search")
        return
    
    # Common browser elements to search for
    search_terms = [
        "address bar",
        "back",
        "forward", 
        "refresh",
        "tab",
        "search",
        "home"
    ]
    
    found_count = 0
    for term in search_terms:
        found = find_web_element_by_description(term, elements)
        if found:
            print(f"✅ Found '{term}': {found['description']} at {found['center']}")
            found_count += 1
        else:
            print(f"❌ '{term}' not found")
    
    print(f"\n📊 Search Results: {found_count}/{len(search_terms)} elements found")

def show_clickable_elements(elements, limit=10):
    """Show top clickable elements"""
    print(f"\n🖱️ Top {limit} Clickable Elements...")
    print("=" * 50)
    
    if not elements or 'error' in elements:
        print("❌ No elements available")
        return
    
    clickable = elements.get('clickable_elements', [])[:limit]
    
    for i, elem in enumerate(clickable, 1):
        print(f"{i:2d}. {elem['description']}")
        print(f"     Location: {elem['center']}")
        print(f"     Type: {elem['element_type']}")

def show_typable_elements(elements, limit=5):
    """Show typable elements"""
    print(f"\n⌨️ Typable Elements (Input Fields)...")
    print("=" * 50)
    
    if not elements or 'error' in elements:
        print("❌ No elements available")
        return
    
    typable = elements.get('typable_elements', [])[:limit]
    
    if not typable:
        print("❌ No typable elements found")
        return
    
    for i, elem in enumerate(typable, 1):
        print(f"{i}. {elem['description']}")
        print(f"   Location: {elem['center']}")
        print(f"   Type: {elem['element_type']}")

def generate_automation_suggestions(elements):
    """Generate GPT-ready automation suggestions"""
    print("\n🤖 Automation Suggestions for GPT...")
    print("=" * 50)
    
    if not elements or 'error' in elements:
        print("❌ No elements for suggestions")
        return
    
    suggestions = []
    
    # Address bar suggestions
    if elements.get('address_bars'):
        addr_bar = elements['address_bars'][0]
        center = addr_bar['bounding_rect']['center_x'], addr_bar['bounding_rect']['center_y']
        suggestions.append(f"• Type \"google.com\" in address bar at {center}")
        suggestions.append(f"• Type \"github.com\" in address bar at {center}")
    
    # Navigation suggestions
    nav_buttons = elements.get('navigation_buttons', [])
    for nav in nav_buttons[:3]:
        center = nav['bounding_rect']['center_x'], nav['bounding_rect']['center_y']
        name = nav['name'].lower()
        if 'back' in name:
            suggestions.append(f"• Click back button at {center}")
        elif 'forward' in name:
            suggestions.append(f"• Click forward button at {center}")
        elif 'refresh' in name or 'reload' in name:
            suggestions.append(f"• Click refresh button at {center}")
    
    # Tab suggestions
    if elements.get('tabs'):
        tab = elements['tabs'][0]
        center = tab['bounding_rect']['center_x'], tab['bounding_rect']['center_y']
        suggestions.append(f"• Click tab \"{tab['name']}\" at {center}")
    
    # Web content suggestions
    web_content = elements.get('web_content', [])
    for content in web_content[:2]:
        if content.get('clickable'):
            center = content['bounding_rect']['center_x'], content['bounding_rect']['center_y']
            suggestions.append(f"• Click \"{content['name']}\" at {center}")
    
    if suggestions:
        print("🎯 Suggested automation actions:")
        for suggestion in suggestions[:8]:  # Limit to 8 suggestions
            print(suggestion)
    else:
        print("❌ No automation suggestions available")

def main():
    """Main test function"""
    print("🌐 WEB BROWSER AUTOMATION TEST")
    print("=" * 60)
    print("This script tests the web browser automation capabilities.")
    print("Make sure you have a browser window open (Chrome, Firefox, Edge, etc.)")
    print("=" * 60)
    
    # Test 1: General browser discovery
    elements = test_browser_discovery()
    
    if not elements or 'error' in elements:
        print("\n❌ Browser discovery failed. Make sure you have a browser open!")
        return
    
    # Test 2: Chrome-specific discovery
    chrome_elements = test_chrome_specific()
    
    # Test 3: Element search
    test_element_search(elements)
    
    # Test 4: Show interactive elements
    show_clickable_elements(elements)
    show_typable_elements(elements)
    
    # Test 5: Generate automation suggestions
    generate_automation_suggestions(elements)
    
    # Test 6: Save detailed results
    print("\n💾 Saving detailed results...")
    with open('browser_automation_results.json', 'w') as f:
        json.dump(elements, f, indent=2)
    print("✅ Results saved to 'browser_automation_results.json'")
    
    print("\n🎉 Browser automation test completed!")
    print("\nNext steps:")
    print("1. Review the results above")
    print("2. Check 'browser_automation_results.json' for detailed element data")
    print("3. Use the suggested automation actions with your GPT integration")

if __name__ == "__main__":
    main() 