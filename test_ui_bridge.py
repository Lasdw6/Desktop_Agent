#!/usr/bin/env python3
"""
Test script for the Rust + Python UI Automation Bridge

This script demonstrates how the bridge works by testing the UI element discovery
and action execution through Python subprocess calls.
"""

import subprocess
import json
import sys
import os

def run_python_script(script_path, *args):
    """Run Python script and return parsed JSON output"""
    try:
        cmd = ["python", script_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="src-py")
        
        if result.returncode != 0:
            print(f"❌ Error running {script_path}: {result.stderr}")
            return None
            
        return json.loads(result.stdout)
    except Exception as e:
        print(f"❌ Exception running {script_path}: {e}")
        return None

def test_ui_discovery():
    """Test UI element discovery"""
    print("🔍 Testing UI Element Discovery...")
    
    # Test basic discovery
    elements = run_python_script("ui_element_discovery.py", "discover")
    if elements:
        if isinstance(elements, dict) and 'error' in elements:
            print(f"⚠️  UI Discovery returned error: {elements['error']}")
        else:
            print(f"✅ Found {len(elements)} UI elements")
            
            # Show some examples
            for i, elem in enumerate(elements[:3]):
                print(f"   {i+1}. {elem['control_type']}: '{elem['name']}' at ({elem['bounding_rect']['center_x']}, {elem['bounding_rect']['center_y']})")
    else:
        print("❌ Failed to get UI elements")
    
    print()

def test_ui_summary():
    """Test UI element summary"""
    print("📊 Testing UI Element Summary...")
    
    summary = run_python_script("ui_element_discovery.py", "summary")
    if summary:
        if isinstance(summary, dict) and 'error' in summary:
            print(f"⚠️  UI Summary returned error: {summary['error']}")
        else:
            print(f"✅ Summary: {summary['total_elements']} total, {summary['clickable_count']} clickable, {summary['typable_count']} typable")
            
            if summary['clickable_elements']:
                print("   Top clickable elements:")
                for elem in summary['clickable_elements'][:3]:
                    print(f"     • {elem['description']} at {elem['center']}")
    else:
        print("❌ Failed to get UI summary")
    
    print()

def test_element_search():
    """Test finding specific elements"""
    print("🎯 Testing Element Search...")
    
    # Try to find a common element
    search_terms = ["button", "text", "menu", "close"]
    
    for term in search_terms:
        element = run_python_script("ui_element_discovery.py", "find", term)
        if element and not ('error' in element):
            print(f"✅ Found element for '{term}': {element['control_type']}: '{element['name']}'")
            break
    else:
        print("⚠️  No common elements found (this might be normal if no UI is open)")
    
    print()

def test_automation_bridge():
    """Test the overall automation bridge concept"""
    print("🔗 Testing Automation Bridge Concept...")
    
    # This simulates what the Rust code would do
    print("1. Rust calls Python to discover UI elements")
    summary = run_python_script("ui_element_discovery.py", "summary")
    
    if summary and not ('error' in summary):
        print("2. Python returns actionable elements to Rust")
        print("3. Rust enhances GPT prompt with available UI elements")
        
        # Create a sample enhanced prompt
        prompt_snippet = f"""
🎯 AVAILABLE UI ELEMENTS:

CLICKABLE ELEMENTS ({summary['clickable_count']} total):"""
        
        for i, elem in enumerate(summary['clickable_elements'][:3]):
            prompt_snippet += f"\n{i+1}. {elem['description']} at {elem['center']}"
        
        prompt_snippet += "\n\n✨ PREFERRED ACTION FORMAT:\n• 'Click the \"[ElementName]\" button' (UI Automation - BEST)\n• 'Click coordinates (x, y)' (Fallback when element not found)"
        
        print("4. Enhanced prompt sent to GPT:")
        print(prompt_snippet)
        
        print("\n5. GPT responds with element-aware actions")
        print("6. Rust executes actions using element names or coordinates")
        print("✅ Bridge workflow complete!")
    else:
        print("⚠️  Bridge test limited due to UI discovery issues")
    
    print()

def main():
    """Main test function"""
    print("🚀 Testing Rust + Python UI Automation Bridge")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists("src-py/ui_element_discovery.py"):
        print("❌ Error: ui_element_discovery.py not found in src-py/")
        print("   Please run this script from the project root directory")
        return 1
    
    # Run tests
    test_ui_discovery()
    test_ui_summary()
    test_element_search()
    test_automation_bridge()
    
    print("🎉 Test complete! The bridge should work with:")
    print("   • Rust calling Python subprocess for UI discovery")
    print("   • Python returning JSON with element information") 
    print("   • Rust parsing JSON and enhancing GPT prompts")
    print("   • Enhanced automation with element-aware actions")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 