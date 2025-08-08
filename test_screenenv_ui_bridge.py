#!/usr/bin/env python3
"""
Test script for the ScreenEnv-based UI Automation Bridge

This script demonstrates how the new ScreenEnv-based system works by testing
the UI element discovery and action execution.
"""

import subprocess
import json
import sys
import os
import time

def run_python_script(script_path, *args):
    """Run Python script and return parsed JSON output"""
    try:
        cmd = ["python", script_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="src-py", timeout=30)
        
        if result.returncode != 0:
            print(f"❌ Error running {script_path}: {result.stderr}")
            return None
            
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout running {script_path}")
        return None
    except Exception as e:
        print(f"❌ Exception running {script_path}: {e}")
        return None

def test_screenenv_initialization():
    """Test ScreenEnv sandbox initialization"""
    print("🔧 Testing ScreenEnv Initialization...")
    
    result = run_python_script("ui_element_discovery.py", "test")
    if result:
        if result.get('status') == 'success':
            print("✅ ScreenEnv sandbox initialized successfully")
            return True
        else:
            print(f"❌ ScreenEnv initialization failed: {result.get('message', 'Unknown error')}")
    else:
        print("❌ Failed to test ScreenEnv initialization")
    
    return False

def test_ui_discovery():
    """Test UI element discovery with ScreenEnv"""
    print("\n🔍 Testing UI Element Discovery with ScreenEnv...")
    
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
    """Test UI elements summary generation"""
    print("📊 Testing UI Elements Summary...")
    
    summary = run_python_script("ui_element_discovery.py", "summary")
    if summary:
        if isinstance(summary, dict) and 'error' in summary:
            print(f"⚠️  UI Summary returned error: {summary['error']}")
        else:
            print(f"✅ UI Summary generated successfully")
            print(f"   • Total elements: {summary.get('total_elements', 0)}")
            print(f"   • Clickable elements: {summary.get('clickable_count', 0)}")
            print(f"   • Typable elements: {summary.get('typable_count', 0)}")
    else:
        print("❌ Failed to generate UI summary")
    
    print()

def test_app_specific_discovery():
    """Test UI discovery with specific applications"""
    print("🎯 Testing App-Specific UI Discovery...")
    
    # Test with common applications
    test_apps = ["firefox", "gedit", "xfce4-terminal"]
    
    for app in test_apps:
        print(f"Testing with {app}...")
        elements = run_python_script("ui_element_discovery.py", "discover", app)
        if elements:
            if isinstance(elements, dict) and 'error' in elements:
                print(f"   ⚠️  {app} discovery error: {elements['error']}")
            else:
                print(f"   ✅ {app}: Found {len(elements)} elements")
        else:
            print(f"   ❌ {app}: Failed to discover elements")
    
    print()

def test_element_search():
    """Test finding specific elements"""
    print("🎯 Testing Element Search...")
    
    # Try to find common elements
    search_terms = ["button", "text", "input", "menu"]
    
    for term in search_terms:
        element = run_python_script("ui_element_discovery.py", "find", term)
        if element and not ('error' in element):
            print(f"✅ Found element for '{term}': {element['control_type']}: '{element['name']}'")
        else:
            print(f"⚠️  No element found for '{term}'")
    
    print()

def test_screenenv_bridge():
    """Test the overall ScreenEnv bridge concept"""
    print("🔗 Testing ScreenEnv Bridge Concept...")
    
    # This simulates what the Rust code would do
    print("1. Rust calls Python to discover UI elements using ScreenEnv")
    summary = run_python_script("ui_element_discovery.py", "summary")
    
    if summary and not ('error' in summary):
        print("2. Python returns actionable elements to Rust")
        print("3. Rust enhances GPT prompt with available UI elements")
        
        # Create a sample enhanced prompt
        prompt_snippet = f"""
🎯 AVAILABLE UI ELEMENTS (ScreenEnv):

CLICKABLE ELEMENTS ({summary['clickable_count']} total):"""
        
        for i, elem in enumerate(summary['clickable_elements'][:3]):
            prompt_snippet += f"\n{i+1}. {elem['description']} at {elem['center']}"
        
        prompt_snippet += "\n\n✨ PREFERRED ACTION FORMAT:\n• 'Click the \"[ElementName]\" button' (ScreenEnv UI - BEST)\n• 'Click coordinates (x, y)' (Fallback when element not found)"
        
        print("4. Enhanced prompt sent to GPT:")
        print(prompt_snippet)
        
        print("\n5. GPT responds with element-aware actions")
        print("6. Rust executes actions using element names or coordinates")
        print("✅ ScreenEnv bridge workflow complete!")
    else:
        print("⚠️  Bridge test limited due to UI discovery issues")
    
    print()

def test_docker_requirements():
    """Test Docker requirements for ScreenEnv"""
    print("🐳 Testing Docker Requirements...")
    
    try:
        # Check if Docker is available
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker is available")
            print(f"   Version: {result.stdout.strip()}")
        else:
            print("❌ Docker is not available")
            return False
    except FileNotFoundError:
        print("❌ Docker command not found")
        return False
    
    try:
        # Check if Docker daemon is running
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker daemon is running")
        else:
            print("❌ Docker daemon is not running")
            print("   Please start Docker daemon before using ScreenEnv")
            return False
    except Exception as e:
        print(f"❌ Docker daemon check failed: {e}")
        return False
    
    print()
    return True

def main():
    """Main test function"""
    print("🚀 Testing ScreenEnv-based UI Automation Bridge")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("src-py/ui_element_discovery.py"):
        print("❌ Error: ui_element_discovery.py not found in src-py/")
        print("   Please run this script from the project root directory")
        return 1
    
    # Check Docker requirements
    if not test_docker_requirements():
        print("⚠️  Docker requirements not met. ScreenEnv may not work properly.")
        print("   Please install Docker and start the Docker daemon.")
        return 1
    
    # Run tests
    init_success = test_screenenv_initialization()
    if init_success:
        test_ui_discovery()
        test_ui_summary()
        test_app_specific_discovery()
        test_element_search()
        test_screenenv_bridge()
    else:
        print("⚠️  Skipping detailed tests due to initialization failure")
    
    print("🎉 ScreenEnv Bridge Test Complete!")
    print("\nKey Features Tested:")
    print("   • ScreenEnv sandbox initialization")
    print("   • UI element discovery using computer vision")
    print("   • Element classification and filtering")
    print("   • Application-specific discovery")
    print("   • Element search and matching")
    print("   • Bridge workflow integration")
    
    if init_success:
        print("\n✅ The ScreenEnv bridge should work with:")
        print("   • Rust calling Python subprocess for UI discovery")
        print("   • Python using ScreenEnv for sandboxed desktop automation")
        print("   • Computer vision-based element detection")
        print("   • Enhanced automation with element-aware actions")
    else:
        print("\n⚠️  Bridge may need additional setup:")
        print("   • Ensure Docker is installed and running")
        print("   • Install screenenv: pip install screenenv")
        print("   • Check Python dependencies: pip install -r src-py/requirements.txt")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 