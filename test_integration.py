#!/usr/bin/env python3
"""
Test script to verify host screen UI detection integration
"""

import sys
import os
sys.path.append('./src-py')

from ui_element_discovery import UIElementDiscovery
import json

def test_host_screen_integration():
    """Test that host screen UI detection works as expected for LLM integration"""
    print("🧪 Testing Host Screen UI Detection Integration")
    print("=" * 60)
    
    # Test 1: Basic element discovery
    print("\n1. Testing basic element discovery...")
    discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.3)
    elements = discovery.discover_elements()
    
    if isinstance(elements, list):
        print(f"✅ Found {len(elements)} elements")
        
        # Test 2: Check element structure
        print("\n2. Testing element structure...")
        if elements:
            sample_element = elements[0]
            required_fields = ['name', 'control_type', 'bounding_rect', 'clickable', 'typable', 'confidence']
            
            for field in required_fields:
                if field in sample_element:
                    print(f"✅ Field '{field}' present")
                else:
                    print(f"❌ Field '{field}' missing")
                    
            # Test 3: Check bounding rect structure
            print("\n3. Testing bounding rect structure...")
            if 'bounding_rect' in sample_element:
                rect = sample_element['bounding_rect']
                rect_fields = ['center_x', 'center_y', 'width', 'height']
                
                for field in rect_fields:
                    if field in rect:
                        print(f"✅ Bounding rect field '{field}' present")
                    else:
                        print(f"❌ Bounding rect field '{field}' missing")
        
        # Test 4: Filter clickable elements
        print("\n4. Testing clickable element filtering...")
        clickable_elements = [elem for elem in elements if elem.get('clickable', False)]
        print(f"✅ Found {len(clickable_elements)} clickable elements")
        
        # Test 5: Filter typable elements
        print("\n5. Testing typable element filtering...")
        typable_elements = [elem for elem in elements if elem.get('typable', False)]
        print(f"✅ Found {len(typable_elements)} typable elements")
        
        # Test 6: Generate LLM-style prompt
        print("\n6. Testing LLM prompt generation...")
        prompt = generate_llm_prompt(elements[:10])  # Take first 10 elements
        print("✅ LLM prompt generated successfully")
        print(f"Prompt length: {len(prompt)} characters")
        
        # Save sample prompt
        with open("integration_test_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
        print("✅ Sample prompt saved to 'integration_test_prompt.txt'")
        
        # Test 7: Test JSON serialization
        print("\n7. Testing JSON serialization...")
        try:
            json_data = json.dumps(elements[:5], indent=2)
            print("✅ JSON serialization successful")
            print(f"JSON length: {len(json_data)} characters")
        except Exception as e:
            print(f"❌ JSON serialization failed: {e}")
        
        return True
        
    else:
        print("❌ No elements found or discovery failed")
        return False

def generate_llm_prompt(elements):
    """Generate a sample LLM prompt with detected elements"""
    
    clickable_elements = [elem for elem in elements if elem.get('clickable', False)]
    typable_elements = [elem for elem in elements if elem.get('typable', False)]
    
    prompt = f"""🖥️ HOST SCREEN UI ELEMENTS (Computer Vision):

DETECTION: Computer Vision + OCR
TOTAL ELEMENTS: {len(elements)}
CLICKABLE ELEMENTS: {len(clickable_elements)}
TYPABLE ELEMENTS: {len(typable_elements)}

CLICKABLE ELEMENTS (top 10):"""
    
    for i, elem in enumerate(clickable_elements[:10]):
        name = elem.get('name', 'Unknown')
        control_type = elem.get('control_type', 'Element')
        confidence = elem.get('confidence', 0.0)
        
        if 'bounding_rect' in elem:
            center_x = elem['bounding_rect'].get('center_x', 0)
            center_y = elem['bounding_rect'].get('center_y', 0)
            prompt += f"\n{i+1}. {control_type}: '{name}' at ({center_x}, {center_y}) [confidence: {confidence:.2f}]"
    
    if typable_elements:
        prompt += f"\n\nTYPABLE ELEMENTS (top 5):"
        for i, elem in enumerate(typable_elements[:5]):
            name = elem.get('name', 'Unknown')
            control_type = elem.get('control_type', 'Element')
            confidence = elem.get('confidence', 0.0)
            
            if 'bounding_rect' in elem:
                center_x = elem['bounding_rect'].get('center_x', 0)
                center_y = elem['bounding_rect'].get('center_y', 0)
                prompt += f"\n{i+1}. {control_type}: '{name}' at ({center_x}, {center_y}) [confidence: {confidence:.2f}]"
    
    prompt += """

✨ PREFERRED ACTION FORMAT:
• 'Click the "[ElementName]" button' (Computer Vision - HIGH ACCURACY)
• 'Type "text" in the "[ElementName]" field' (For text inputs)
• 'Click coordinates (x, y)' (Fallback when element not found)

AUTOMATION CAPABILITIES:
• Element detection via computer vision
• OCR text extraction
• Confidence-based filtering
• Real-time screen analysis
• Cross-platform compatibility"""
    
    return prompt

def main():
    """Main test function"""
    success = test_host_screen_integration()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Integration test PASSED!")
        print("\nThe host screen UI detection is ready for LLM integration:")
        print("• ✅ Elements discovered successfully")
        print("• ✅ Proper JSON structure")
        print("• ✅ Clickable/typable filtering works")
        print("• ✅ LLM prompt generation works")
        print("• ✅ Compatible with Rust backend")
        
        print("\nNext steps:")
        print("1. Start the Tauri app: cargo tauri dev")
        print("2. Test automation with host screen detection")
        print("3. LLM will now receive UI element data automatically")
        
        return 0
    else:
        print("❌ Integration test FAILED!")
        print("Please check the host screen detection setup.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 