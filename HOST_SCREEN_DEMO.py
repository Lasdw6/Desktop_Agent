#!/usr/bin/env python3
"""
Host Screen UI Detection Demo

This script demonstrates how to use the computer vision-based UI detection
to find and interact with elements on your actual desktop screen.
"""

import sys
import os
import time
import json

# Add src-py to path
sys.path.append('src-py')

from ui_element_discovery import UIElementDiscovery, get_actionable_elements_summary, find_element_by_description
import pyautogui

def demo_basic_discovery():
    """Basic UI element discovery demo"""
    print("🔍 Demo: Basic UI Element Discovery")
    print("=" * 50)
    
    print("Analyzing your current screen...")
    
    # Create discovery instance
    discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.3)
    
    # Discover elements
    elements = discovery.discover_elements()
    
    if isinstance(elements, list) and elements:
        print(f"✅ Found {len(elements)} interactive elements")
        
        # Show top elements
        print("\n🏆 Top detected elements:")
        for i, elem in enumerate(elements[:3]):
            confidence = elem.get('confidence', 0.0)
            center_x = elem['bounding_rect']['center_x']
            center_y = elem['bounding_rect']['center_y']
            print(f"{i+1}. {elem['control_type']}: '{elem['name']}'")
            print(f"   Position: ({center_x}, {center_y})")
            print(f"   Confidence: {confidence:.2f}")
            print(f"   Clickable: {elem.get('clickable', False)}")
            print(f"   Typable: {elem.get('typable', False)}")
            print()
        
        return elements
    else:
        print("⚠️  No elements detected. Try opening an application first.")
        return []

def demo_visual_debug():
    """Visual debugging demo"""
    print("\n🖼️ Demo: Visual Debug Output")
    print("=" * 50)
    
    print("Creating debug image with detected elements...")
    
    discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.3)
    elements = discovery.discover_elements()
    
    if isinstance(elements, list) and elements:
        # Save debug image
        debug_file = "ui_detection_debug.png"
        discovery.save_debug_image(debug_file)
        
        if os.path.exists(debug_file):
            print(f"✅ Debug image saved: {debug_file}")
            print("   • Green rectangles: Clickable elements")
            print("   • Cyan rectangles: Text input fields")
            print("   • Red rectangles: Other elements")
            print("   • Labels show element names and confidence scores")
            print(f"   • Open '{debug_file}' to see the visualization")
        else:
            print("❌ Failed to save debug image")
    else:
        print("⚠️  No elements to visualize")

def demo_element_search():
    """Element search demo"""
    print("\n🎯 Demo: Element Search")
    print("=" * 50)
    
    discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.3)
    elements = discovery.discover_elements()
    
    if isinstance(elements, list) and elements:
        # Try to find common elements
        search_terms = ["close", "file", "edit", "button", "menu"]
        
        print("Searching for common UI elements...")
        found_elements = []
        
        for term in search_terms:
            found = find_element_by_description(term, elements)
            if found:
                confidence = found.get('confidence', 0.0)
                center_x = found['bounding_rect']['center_x']
                center_y = found['bounding_rect']['center_y']
                print(f"✅ Found '{term}': {found['control_type']}: '{found['name']}'")
                print(f"   Position: ({center_x}, {center_y}), Confidence: {confidence:.2f}")
                found_elements.append((term, found))
            else:
                print(f"⚠️  '{term}' not found")
        
        return found_elements
    else:
        print("⚠️  No elements available for search")
        return []

def demo_simulated_automation():
    """Simulated automation demo (shows coordinates, doesn't actually click)"""
    print("\n🤖 Demo: Simulated Automation")
    print("=" * 50)
    
    discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.5)
    elements = discovery.discover_elements()
    
    if isinstance(elements, list) and elements:
        # Find a high-confidence clickable element
        clickable_elements = [elem for elem in elements if elem.get('clickable', False)]
        
        if clickable_elements:
            # Sort by confidence
            clickable_elements.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            target = clickable_elements[0]
            
            center_x = target['bounding_rect']['center_x']
            center_y = target['bounding_rect']['center_y']
            confidence = target.get('confidence', 0.0)
            
            print(f"🎯 Target Element: {target['control_type']}: '{target['name']}'")
            print(f"   Position: ({center_x}, {center_y})")
            print(f"   Confidence: {confidence:.2f}")
            print()
            
            # Simulate automation commands
            print("Simulated automation commands:")
            print(f"1. Move mouse to ({center_x}, {center_y})")
            print(f"2. Click left mouse button")
            print()
            
            # Ask if user wants to actually perform the action
            response = input("Actually perform this click? (y/n): ")
            if response.lower() == 'y':
                print("Performing click in 3 seconds...")
                for i in range(3, 0, -1):
                    print(f"   {i}...")
                    time.sleep(1)
                
                # Perform the actual click
                pyautogui.click(center_x, center_y)
                print("✅ Click performed!")
            else:
                print("✅ Simulation complete (no actual click)")
        else:
            print("⚠️  No clickable elements found")
    else:
        print("⚠️  No elements available for automation")

def demo_gpt_integration():
    """Demo GPT integration format"""
    print("\n🧠 Demo: GPT Integration Format")
    print("=" * 50)
    
    discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.4)
    elements = discovery.discover_elements()
    
    if isinstance(elements, list) and elements:
        summary = get_actionable_elements_summary(elements)
        
        # Create GPT-style prompt
        prompt = f"""
🎯 AVAILABLE UI ELEMENTS (Host Screen):

PLATFORM: {summary.get('platform', 'Unknown')}
DETECTION: {summary.get('detection_method', 'Unknown')}
TOTAL ELEMENTS: {summary.get('total_elements', 0)}

CLICKABLE ELEMENTS ({summary['clickable_count']} total):"""
        
        for i, elem in enumerate(summary['clickable_elements'][:5]):
            confidence = elem.get('confidence', 0.0)
            prompt += f"\n{i+1}. {elem['description']} at {elem['center']} [confidence: {confidence:.2f}]"
        
        if summary['typable_count'] > 0:
            prompt += f"\n\nTYPABLE ELEMENTS ({summary['typable_count']} total):"
            for i, elem in enumerate(summary['typable_elements'][:3]):
                confidence = elem.get('confidence', 0.0)
                prompt += f"\n{i+1}. {elem['description']} at {elem['center']} [confidence: {confidence:.2f}]"
        
        prompt += "\n\n✨ PREFERRED ACTION FORMAT:\n"
        prompt += "• 'Click the \"[ElementName]\" button' (Computer Vision - BEST)\n"
        prompt += "• 'Click coordinates (x, y)' (Fallback when element not found)\n"
        prompt += "• 'Type \"text\" in the \"[ElementName]\" field' (For text inputs)\n"
        
        print("Sample GPT prompt with detected elements:")
        print(prompt)
        
        # Save to file
        with open("gpt_prompt_sample.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"\n✅ Full prompt saved to 'gpt_prompt_sample.txt'")
        
    else:
        print("⚠️  No elements available for GPT integration")

def main():
    """Main demo function"""
    print("🚀 Host Screen UI Detection Demo")
    print("=" * 60)
    print()
    print("This demo shows how to detect and interact with UI elements")
    print("on your actual desktop screen using computer vision.")
    print()
    print("Make sure you have some applications open for better results!")
    print()
    
    # Check dependencies
    try:
        import cv2
        import numpy as np
        from PIL import Image
        import pytesseract
        print("✅ All required dependencies are available")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install: pip install -r src-py/requirements.txt")
        return 1
    
    print()
    input("Press Enter to start the demo...")
    print()
    
    # Run demo sections
    elements = demo_basic_discovery()
    
    if elements:
        demo_visual_debug()
        found_elements = demo_element_search()
        
        if found_elements:
            demo_simulated_automation()
        
        demo_gpt_integration()
    
    print("\n" + "=" * 60)
    print("🎉 Demo Complete!")
    print()
    print("Key Takeaways:")
    print("• ✅ Works with your actual desktop (no Docker needed)")
    print("• ✅ Uses computer vision to detect UI elements")
    print("• ✅ OCR extracts text from buttons and fields")
    print("• ✅ Confidence scores help identify reliable elements")
    print("• ✅ Compatible with existing Rust backend")
    print("• ✅ Generates GPT-ready prompts")
    print()
    print("Next Steps:")
    print("1. Open some applications and run the demo again")
    print("2. Check the debug image to see detected elements")
    print("3. Use the JSON API in your Rust application")
    print("4. Experiment with different confidence thresholds")
    print()
    print("Files Created:")
    print("• ui_detection_debug.png - Visual debug image")
    print("• gpt_prompt_sample.txt - Sample GPT prompt")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 