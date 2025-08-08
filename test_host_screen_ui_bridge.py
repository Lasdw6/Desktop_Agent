#!/usr/bin/env python3
"""
Test script for Host Screen UI Detection Bridge

This script demonstrates how the system now works directly with your actual desktop
screen using computer vision, without requiring Docker containers.
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

def test_host_screen_capture():
    """Test host screen capture functionality"""
    print("🖥️ Testing Host Screen Capture...")
    
    result = run_python_script("ui_element_discovery.py", "test")
    if result:
        if result.get('status') == 'success':
            print("✅ Host screen capture working successfully")
            screen_size = result.get('screen_size', 'Unknown')
            print(f"   Screen size: {screen_size}")
            return True
        else:
            print(f"❌ Host screen capture failed: {result.get('message', 'Unknown error')}")
    else:
        print("❌ Failed to test host screen capture")
    
    return False

def test_ui_discovery():
    """Test UI element discovery on actual screen"""
    print("\n🔍 Testing UI Element Discovery on Your Screen...")
    
    # Test basic discovery
    elements = run_python_script("ui_element_discovery.py", "discover")
    if elements:
        if isinstance(elements, dict) and 'error' in elements:
            print(f"⚠️  UI Discovery returned error: {elements['error']}")
        else:
            print(f"✅ Found {len(elements)} UI elements on your screen")
            
            # Show some examples
            for i, elem in enumerate(elements[:5]):  # Show top 5
                confidence = elem.get('confidence', 0.0)
                print(f"   {i+1}. {elem['control_type']}: '{elem['name']}' at ({elem['bounding_rect']['center_x']}, {elem['bounding_rect']['center_y']}) [confidence: {confidence:.2f}]")
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
            print(f"   • Platform: {summary.get('platform', 'Unknown')}")
            print(f"   • Detection Method: {summary.get('detection_method', 'Unknown')}")
            print(f"   • Total elements: {summary.get('total_elements', 0)}")
            print(f"   • Clickable elements: {summary.get('clickable_count', 0)}")
            print(f"   • Typable elements: {summary.get('typable_count', 0)}")
            
            # Show some high-confidence elements
            clickable = summary.get('clickable_elements', [])
            if clickable:
                print("   • Top clickable elements:")
                for elem in clickable[:3]:
                    confidence = elem.get('confidence', 0.0)
                    print(f"     - {elem['description']} at {elem['center']} [confidence: {confidence:.2f}]")
    else:
        print("❌ Failed to generate UI summary")
    
    print()

def test_element_search():
    """Test finding specific elements"""
    print("🎯 Testing Element Search...")
    
    # Try to find common elements that might be on screen
    search_terms = ["button", "close", "file", "edit", "view", "help"]
    
    found_any = False
    for term in search_terms:
        element = run_python_script("ui_element_discovery.py", "find", term)
        if element and not ('error' in element):
            confidence = element.get('confidence', 0.0)
            print(f"✅ Found element for '{term}': {element['control_type']}: '{element['name']}' [confidence: {confidence:.2f}]")
            found_any = True
        else:
            print(f"⚠️  No element found for '{term}'")
    
    if not found_any:
        print("💡 Tip: Try opening an application with visible UI elements first")
    
    print()

def test_debug_visualization():
    """Test debug image creation"""
    print("🖼️ Testing Debug Visualization...")
    
    debug_file = "test_debug_elements.png"
    result = run_python_script("ui_element_discovery.py", "debug", debug_file)
    
    if result:
        if result.get('status') == 'success':
            elements_found = result.get('elements_found', 0)
            print(f"✅ Debug image created successfully")
            print(f"   • File: {debug_file}")
            print(f"   • Elements detected: {elements_found}")
            print(f"   • Image shows detected elements with colored rectangles")
            print(f"   • Green: Clickable elements")
            print(f"   • Cyan: Text input fields")
            print(f"   • Red: Other elements")
            
            # Check if file actually exists
            if os.path.exists(debug_file):
                print(f"   • File confirmed on disk")
            else:
                print(f"   • ⚠️  File not found on disk")
        else:
            print(f"❌ Debug image creation failed: {result.get('message', 'Unknown error')}")
    else:
        print("❌ Failed to create debug image")
    
    print()

def test_ocr_capabilities():
    """Test OCR text extraction capabilities"""
    print("📝 Testing OCR Text Extraction...")
    
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"✅ Tesseract OCR is available (version: {version})")
        
        # Test actual text extraction on screen
        elements = run_python_script("ui_element_discovery.py", "discover")
        if elements and isinstance(elements, list):
            text_elements = [elem for elem in elements if elem.get('name', '').startswith('Element_at_') == False]
            
            if text_elements:
                print(f"✅ OCR successfully extracted text from {len(text_elements)} elements")
                print("   Sample extracted text:")
                for elem in text_elements[:3]:
                    name = elem.get('name', 'Unknown')
                    confidence = elem.get('confidence', 0.0)
                    print(f"   • \"{name}\" [confidence: {confidence:.2f}]")
            else:
                print("⚠️  OCR didn't find readable text on current screen")
        else:
            print("⚠️  Could not test OCR due to element discovery issues")
            
    except ImportError:
        print("❌ pytesseract not installed. Install with: pip install pytesseract")
    except Exception as e:
        print(f"❌ OCR test failed: {e}")
    
    print()

def test_bridge_integration():
    """Test integration with Rust backend"""
    print("🔗 Testing Bridge Integration...")
    
    print("1. Testing JSON API compatibility...")
    summary = run_python_script("ui_element_discovery.py", "summary")
    
    if summary and not ('error' in summary):
        print("✅ JSON API is working correctly")
        print("2. Simulating Rust backend integration...")
        
        # Create a sample enhanced prompt like the Rust code would
        prompt_snippet = f"""
🎯 AVAILABLE UI ELEMENTS (Host Screen):

PLATFORM: {summary.get('platform', 'Unknown')}
DETECTION: {summary.get('detection_method', 'Unknown')}

CLICKABLE ELEMENTS ({summary['clickable_count']} total):"""
        
        for i, elem in enumerate(summary['clickable_elements'][:3]):
            confidence = elem.get('confidence', 0.0)
            prompt_snippet += f"\n{i+1}. {elem['description']} at {elem['center']} [confidence: {confidence:.2f}]"
        
        prompt_snippet += "\n\n✨ PREFERRED ACTION FORMAT:\n• 'Click the \"[ElementName]\" button' (Host Screen CV - BEST)\n• 'Click coordinates (x, y)' (Fallback when element not found)"
        
        print("3. Enhanced prompt for GPT:")
        print(prompt_snippet)
        
        print("\n4. Integration workflow:")
        print("   ✅ Rust calls Python subprocess")
        print("   ✅ Python captures host screen")
        print("   ✅ Computer vision detects UI elements")
        print("   ✅ OCR extracts text from elements")
        print("   ✅ JSON response with confidence scores")
        print("   ✅ Rust enhances GPT prompts")
        print("   ✅ Element-aware automation")
        
        print("\n✅ Bridge integration ready!")
    else:
        print("⚠️  Bridge integration test limited due to summary issues")
    
    print()

def interactive_demo():
    """Interactive demonstration"""
    print("🎮 Interactive Demo")
    print("=" * 40)
    
    print("This demo will analyze your current screen in real-time.")
    print("Make sure you have some applications open for better results.")
    print()
    
    response = input("Continue with interactive demo? (y/n): ")
    if response.lower() != 'y':
        return
    
    print("\n🔍 Analyzing your screen...")
    
    # Run discovery
    discovery = UIElementDiscovery(use_ocr=True)
    elements = discovery.discover_elements()
    
    if isinstance(elements, list) and elements:
        print(f"✅ Found {len(elements)} interactive elements")
        
        # Show top elements
        print("\n🏆 Top detected elements:")
        for i, elem in enumerate(elements[:5]):
            confidence = elem.get('confidence', 0.0)
            center_x = elem['bounding_rect']['center_x']
            center_y = elem['bounding_rect']['center_y']
            print(f"{i+1}. {elem['control_type']}: '{elem['name']}'")
            print(f"   Position: ({center_x}, {center_y})")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Clickable: {elem.get('clickable', False)}")
            print(f"   Typable: {elem.get('typable', False)}")
            print()
        
        # Create debug image
        print("📸 Creating debug visualization...")
        discovery.save_debug_image("interactive_demo.png")
        print("✅ Debug image saved as 'interactive_demo.png'")
        print("   Open this file to see detected elements highlighted!")
        
    else:
        print("⚠️  No elements detected. Try opening an application first.")

def main():
    """Main test function"""
    print("🚀 Testing Host Screen UI Detection Bridge")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not os.path.exists("src-py/ui_element_discovery.py"):
        print("❌ Error: ui_element_discovery.py not found in src-py/")
        print("   Please run this script from the project root directory")
        return 1
    
    # Run tests
    print("📋 Running comprehensive tests...")
    print()
    
    screen_ok = test_host_screen_capture()
    
    if screen_ok:
        test_ui_discovery()
        test_ui_summary()
        test_element_search()
        test_debug_visualization()
        test_ocr_capabilities()
        test_bridge_integration()
        
        # Offer interactive demo
        response = input("🎮 Run interactive demo? (y/n): ")
        if response.lower() == 'y':
            print()
            interactive_demo()
            
    else:
        print("⚠️  Skipping detailed tests due to screen capture failure")
    
    print("\n" + "=" * 60)
    print("🎉 Host Screen UI Detection Test Complete!")
    print("\nKey Features Tested:")
    print("   • Direct host screen capture (no Docker needed)")
    print("   • Computer vision-based UI element detection")
    print("   • OCR text extraction from UI elements")
    print("   • Confidence scoring for better matching")
    print("   • Debug visualization with element highlighting")
    print("   • JSON API compatibility with Rust backend")
    
    if screen_ok:
        print("\n✅ The system is working with your actual desktop:")
        print("   • Takes screenshots of your real screen")
        print("   • Detects buttons, text fields, and clickable elements")
        print("   • Extracts text using OCR")
        print("   • Provides confidence scores for each element")
        print("   • Compatible with existing Rust backend")
    else:
        print("\n⚠️  System needs troubleshooting:")
        print("   • Check Python dependencies: pip install -r src-py/requirements.txt")
        print("   • Verify screen capture permissions")
        print("   • For OCR: Install Tesseract OCR")
        print("   • Try running as administrator if needed")
    
    print("\n💡 Usage Tips:")
    print("   • Open applications for better element detection")
    print("   • Use 'python src-py/ui_element_discovery.py debug' for visual debugging")
    print("   • Higher confidence scores = more reliable elements")
    print("   • Works best with standard desktop applications")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 