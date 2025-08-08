# UI Element Discovery using Computer Vision on Host Screen
# This script finds all interactive UI elements on the actual desktop using computer vision

import json
import sys
import traceback
from typing import List, Dict, Any, Optional
import time
import base64
import io
import cv2
import numpy as np
from PIL import Image, ImageGrab
import logging
from mss import mss
import pytesseract
import platform

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UIElementInfo:
    """Represents information about a UI element detected on the desktop"""
    def __init__(self, element_data: Dict[str, Any]):
        self.name = element_data.get('name', 'Unknown')
        self.element_type = element_data.get('type', 'Unknown')
        self.bounding_rect = element_data.get('bounding_rect', {})
        self.center = element_data.get('center', (0, 0))
        self.is_enabled = element_data.get('is_enabled', True)
        self.is_visible = element_data.get('is_visible', True)
        self.is_clickable = element_data.get('is_clickable', False)
        self.is_typable = element_data.get('is_typable', False)
        self.class_name = element_data.get('class_name', '')
        self.automation_id = element_data.get('automation_id', '')
        self.help_text = element_data.get('help_text', '')
        self.access_key = element_data.get('access_key', '')
        self.confidence = element_data.get('confidence', 0.0)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'name': self.name,
            'control_type': self.element_type,
            'automation_id': self.automation_id,
            'class_name': self.class_name,
            'bounding_rect': {
                'left': self.bounding_rect.get('left', 0),
                'top': self.bounding_rect.get('top', 0),
                'right': self.bounding_rect.get('right', 0),
                'bottom': self.bounding_rect.get('bottom', 0),
                'width': self.bounding_rect.get('width', 0),
                'height': self.bounding_rect.get('height', 0),
                'center_x': self.center[0],
                'center_y': self.center[1]
            },
            'is_enabled': self.is_enabled,
            'is_visible': self.is_visible,
            'help_text': self.help_text,
            'access_key': self.access_key,
            'clickable': self.is_clickable,
            'typable': self.is_typable,
            'confidence': self.confidence
        }

class UIElementDiscovery:
    """Main class for discovering UI elements on the host screen using computer vision"""
    
    def __init__(self, use_ocr: bool = True, confidence_threshold: float = 0.5):
        self.use_ocr = use_ocr
        self.confidence_threshold = confidence_threshold
        self.found_elements: List[UIElementInfo] = []
        
        # Check if OCR is available
        if self.use_ocr:
            try:
                pytesseract.get_tesseract_version()
                logger.info("OCR (Tesseract) is available")
            except Exception as e:
                logger.warning(f"OCR not available: {e}")
                self.use_ocr = False
        
    def _capture_screen(self) -> np.ndarray:
        """Capture the current screen"""
        try:
            # Use mss for cross-platform screen capture
            with mss() as sct:
                # Get the primary monitor
                monitor = sct.monitors[1]
                
                # Take screenshot
                screenshot = sct.grab(monitor)
                
                # Convert to numpy array
                img_array = np.array(screenshot)
                
                # Convert BGRA to BGR (remove alpha channel)
                if img_array.shape[2] == 4:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
                
                return img_array
                
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            # Fallback to PIL
            try:
                screenshot = ImageGrab.grab()
                img_array = np.array(screenshot)
                # Convert RGB to BGR for OpenCV
                if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                return img_array
            except Exception as e2:
                logger.error(f"Fallback screen capture also failed: {e2}")
                raise
    
    def _detect_ui_elements_from_screenshot(self, screenshot: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect UI elements from screenshot using computer vision techniques
        """
        elements = []
        
        try:
            # Convert to grayscale for processing
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            # Apply different detection methods
            elements.extend(self._detect_buttons(screenshot, gray))
            elements.extend(self._detect_text_fields(screenshot, gray))
            elements.extend(self._detect_clickable_elements(screenshot, gray))
            
            # Remove duplicates based on position
            elements = self._remove_duplicate_elements(elements)
            
            # Sort by confidence and position
            elements.sort(key=lambda x: (-x.get('confidence', 0), x['bounding_rect']['top'], x['bounding_rect']['left']))
            
        except Exception as e:
            logger.error(f"Error detecting UI elements: {e}")
            
        return elements
    
    def _detect_buttons(self, screenshot: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect button-like elements"""
        elements = []
        
        try:
            # Apply edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # Filter by area (button-like size)
                if area < 300 or area > 20000:
                    continue
                
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Button-like aspect ratio
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 0.5 or aspect_ratio > 8:
                    continue
                
                # Check if it looks like a button (rectangular with moderate size)
                if 20 <= h <= 80 and 40 <= w <= 400:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Extract text from button
                    element_name = self._extract_text_from_region(screenshot, x, y, w, h)
                    
                    if not element_name:
                        element_name = f"Button_{i}"
                    
                    confidence = self._calculate_button_confidence(screenshot, x, y, w, h)
                    
                    element_data = {
                        'name': element_name,
                        'type': 'Button',
                        'bounding_rect': {
                            'left': x,
                            'top': y,
                            'right': x + w,
                            'bottom': y + h,
                            'width': w,
                            'height': h
                        },
                        'center': (center_x, center_y),
                        'is_enabled': True,
                        'is_visible': True,
                        'is_clickable': True,
                        'is_typable': False,
                        'class_name': '',
                        'automation_id': f'button_{i}',
                        'help_text': '',
                        'access_key': '',
                        'confidence': confidence
                    }
                    
                    elements.append(element_data)
                    
        except Exception as e:
            logger.error(f"Error detecting buttons: {e}")
            
        return elements
    
    def _detect_text_fields(self, screenshot: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect text input fields"""
        elements = []
        
        try:
            # Apply morphological operations to detect text field shapes
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            processed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            
            # Find contours
            contours, _ = cv2.findContours(processed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for i, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                
                # Filter by area (text field size)
                if area < 500 or area > 50000:
                    continue
                
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Text field-like aspect ratio (wide and not too tall)
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 2 or aspect_ratio > 15:
                    continue
                
                # Check if it looks like a text field
                if 15 <= h <= 50 and 80 <= w <= 800:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Extract text or placeholder
                    element_name = self._extract_text_from_region(screenshot, x, y, w, h)
                    
                    if not element_name:
                        element_name = f"TextInput_{i}"
                    
                    confidence = self._calculate_textfield_confidence(screenshot, x, y, w, h)
                    
                    element_data = {
                        'name': element_name,
                        'type': 'Edit',
                        'bounding_rect': {
                            'left': x,
                            'top': y,
                            'right': x + w,
                            'bottom': y + h,
                            'width': w,
                            'height': h
                        },
                        'center': (center_x, center_y),
                        'is_enabled': True,
                        'is_visible': True,
                        'is_clickable': True,
                        'is_typable': True,
                        'class_name': '',
                        'automation_id': f'textfield_{i}',
                        'help_text': '',
                        'access_key': '',
                        'confidence': confidence
                    }
                    
                    elements.append(element_data)
                    
        except Exception as e:
            logger.error(f"Error detecting text fields: {e}")
            
        return elements
    
    def _detect_clickable_elements(self, screenshot: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect other clickable elements (links, menu items, etc.)"""
        elements = []
        
        try:
            # Use template matching for common UI patterns
            # This is a simplified approach - in production, you'd use more sophisticated methods
            
            # Detect potential clickable areas using corner detection
            corners = cv2.goodFeaturesToTrack(gray, maxCorners=100, qualityLevel=0.01, minDistance=30)
            
            if corners is not None:
                for i, corner in enumerate(corners):
                    x, y = corner.ravel()
                    x, y = int(x), int(y)
                    
                    # Create a small region around the corner
                    w, h = 60, 25
                    x = max(0, x - w//2)
                    y = max(0, y - h//2)
                    
                    # Make sure we don't go out of bounds
                    if x + w >= screenshot.shape[1] or y + h >= screenshot.shape[0]:
                        continue
                    
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Extract text from the region
                    element_name = self._extract_text_from_region(screenshot, x, y, w, h)
                    
                    if not element_name or len(element_name.strip()) < 2:
                        continue
                    
                    confidence = 0.3  # Lower confidence for generic clickable elements
                    
                    element_data = {
                        'name': element_name,
                        'type': 'Link',
                        'bounding_rect': {
                            'left': x,
                            'top': y,
                            'right': x + w,
                            'bottom': y + h,
                            'width': w,
                            'height': h
                        },
                        'center': (center_x, center_y),
                        'is_enabled': True,
                        'is_visible': True,
                        'is_clickable': True,
                        'is_typable': False,
                        'class_name': '',
                        'automation_id': f'clickable_{i}',
                        'help_text': '',
                        'access_key': '',
                        'confidence': confidence
                    }
                    
                    elements.append(element_data)
                    
        except Exception as e:
            logger.error(f"Error detecting clickable elements: {e}")
            
        return elements
    
    def _extract_text_from_region(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> str:
        """Extract text from a specific region using OCR"""
        try:
            if not self.use_ocr:
                return f"Element_at_{x}_{y}"
            
            # Extract the region
            roi = image[y:y+h, x:x+w]
            
            # Convert to grayscale for better OCR
            if len(roi.shape) == 3:
                roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            else:
                roi_gray = roi
            
            # Apply some preprocessing for better OCR
            # Resize if too small
            if roi_gray.shape[0] < 20 or roi_gray.shape[1] < 20:
                roi_gray = cv2.resize(roi_gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            
            # Apply thresholding to get better contrast
            _, roi_thresh = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Use OCR to extract text
            text = pytesseract.image_to_string(roi_thresh, config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ')
            
            # Clean up the text
            text = text.strip()
            
            # Remove non-printable characters
            text = ''.join(char for char in text if char.isprintable())
            
            # If text is too short or looks like garbage, return a position-based name
            if len(text) < 2 or len(text) > 50:
                return f"Element_at_{x}_{y}"
            
            return text
            
        except Exception as e:
            logger.debug(f"OCR failed for region ({x},{y},{w},{h}): {e}")
            return f"Element_at_{x}_{y}"
    
    def _calculate_button_confidence(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> float:
        """Calculate confidence score for button detection"""
        try:
            # Extract the region
            roi = image[y:y+h, x:x+w]
            
            # Convert to grayscale
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Check for button-like characteristics
            confidence = 0.5  # Base confidence
            
            # Check for uniform color (buttons often have solid backgrounds)
            std_dev = np.std(gray_roi)
            if std_dev < 30:  # Relatively uniform
                confidence += 0.2
            
            # Check for rectangular shape
            edges = cv2.Canny(gray_roi, 50, 150)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                # Check if the contour is roughly rectangular
                peri = cv2.arcLength(largest_contour, True)
                approx = cv2.approxPolyDP(largest_contour, 0.02 * peri, True)
                
                if len(approx) == 4:  # Roughly rectangular
                    confidence += 0.2
            
            return min(confidence, 1.0)
            
        except Exception:
            return 0.5
    
    def _calculate_textfield_confidence(self, image: np.ndarray, x: int, y: int, w: int, h: int) -> float:
        """Calculate confidence score for text field detection"""
        try:
            # Extract the region
            roi = image[y:y+h, x:x+w]
            
            # Convert to grayscale
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            
            # Check for text field-like characteristics
            confidence = 0.5  # Base confidence
            
            # Check aspect ratio (text fields are typically wide)
            aspect_ratio = w / h if h > 0 else 0
            if 3 <= aspect_ratio <= 12:
                confidence += 0.2
            
            # Check for border (text fields often have borders)
            edges = cv2.Canny(gray_roi, 50, 150)
            border_pixels = np.sum(edges > 0)
            
            if border_pixels > 0:
                confidence += 0.2
            
            return min(confidence, 1.0)
            
        except Exception:
            return 0.5
    
    def _remove_duplicate_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate elements that are too close to each other"""
        if not elements:
            return elements
        
        unique_elements = []
        
        for element in elements:
            is_duplicate = False
            center_x, center_y = element['center']
            
            for existing in unique_elements:
                existing_x, existing_y = existing['center']
                
                # Calculate distance between centers
                distance = np.sqrt((center_x - existing_x)**2 + (center_y - existing_y)**2)
                
                # If elements are too close, consider them duplicates
                if distance < 30:
                    is_duplicate = True
                    # Keep the one with higher confidence
                    if element.get('confidence', 0) > existing.get('confidence', 0):
                        unique_elements.remove(existing)
                        unique_elements.append(element)
                    break
            
            if not is_duplicate:
                unique_elements.append(element)
        
        return unique_elements
    
    def discover_elements(self, focus_application: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover all interactive UI elements on the current screen
        
        Args:
            focus_application: Optional application to focus on (not used in host mode)
            
        Returns:
            List of element dictionaries or error dict
        """
        try:
            logger.info("Discovering UI elements on host screen...")
            
            # Capture the current screen
            screenshot = self._capture_screen()
            
            if screenshot is None:
                return {'error': 'Failed to capture screen'}
            
            # Detect UI elements from screenshot
            elements_data = self._detect_ui_elements_from_screenshot(screenshot)
            
            # Filter by confidence threshold
            elements_data = [elem for elem in elements_data if elem.get('confidence', 0) >= self.confidence_threshold]
            
            # Convert to UIElementInfo objects
            self.found_elements = [UIElementInfo(data) for data in elements_data]
            
            # Filter and sort elements
            interactive_elements = [elem.to_dict() for elem in self.found_elements 
                                  if elem.is_enabled and elem.is_visible and 
                                  (elem.is_clickable or elem.is_typable)]
            
            # Sort by confidence, then position (top to bottom, left to right)
            interactive_elements.sort(key=lambda x: (-x.get('confidence', 0), x['bounding_rect']['top'], 
                                                   x['bounding_rect']['left']))
            
            logger.info(f"Discovered {len(interactive_elements)} interactive elements")
            return interactive_elements
            
        except Exception as e:
            logger.error(f"Failed to discover elements: {e}")
            return {'error': f'Failed to discover elements: {str(e)}', 'traceback': traceback.format_exc()}
    
    def save_debug_image(self, output_path: str = "debug_elements.png"):
        """Save a debug image showing detected elements"""
        try:
            screenshot = self._capture_screen()
            
            # Draw rectangles around detected elements
            for element in self.found_elements:
                rect = element.bounding_rect
                x, y, w, h = rect['left'], rect['top'], rect['width'], rect['height']
                
                # Choose color based on element type
                if element.is_clickable and element.is_typable:
                    color = (0, 255, 255)  # Cyan for input fields
                elif element.is_clickable:
                    color = (0, 255, 0)    # Green for clickable
                else:
                    color = (255, 0, 0)    # Red for others
                
                # Draw rectangle
                cv2.rectangle(screenshot, (x, y), (x + w, y + h), color, 2)
                
                # Draw label
                label = f"{element.name} ({element.confidence:.2f})"
                cv2.putText(screenshot, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
            # Save the image
            cv2.imwrite(output_path, screenshot)
            logger.info(f"Debug image saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save debug image: {e}")

def get_actionable_elements_summary(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a summary of actionable elements for GPT prompts
    
    Args:
        elements: List of discovered elements
        
    Returns:
        Summary dictionary
    """
    if not elements or isinstance(elements, dict):
        return {'error': 'No elements to summarize'}
    
    clickable_elements = [elem for elem in elements if elem.get('clickable', False)]
    typable_elements = [elem for elem in elements if elem.get('typable', False)]
    
    # Create element info for summary
    clickable_info = []
    for elem in clickable_elements[:10]:  # Limit to top 10
        center = elem['bounding_rect']
        clickable_info.append({
            'name': elem['name'],
            'type': elem['control_type'],
            'center': (center['center_x'], center['center_y']),
            'description': f"{elem['control_type']}: '{elem['name']}'",
            'confidence': elem.get('confidence', 0.0)
        })
    
    typable_info = []
    for elem in typable_elements[:5]:  # Limit to top 5
        center = elem['bounding_rect']
        typable_info.append({
            'name': elem['name'],
            'type': elem['control_type'],
            'center': (center['center_x'], center['center_y']),
            'description': f"{elem['control_type']}: '{elem['name']}'",
            'confidence': elem.get('confidence', 0.0)
        })
    
    return {
        'total_elements': len(elements),
        'clickable_count': len(clickable_elements),
        'typable_count': len(typable_elements),
        'clickable_elements': clickable_info,
        'typable_elements': typable_info,
        'platform': platform.system(),
        'detection_method': 'Computer Vision + OCR'
    }

def find_element_by_description(description: str, elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find element by natural language description
    
    Args:
        description: Natural language description of element
        elements: List of discovered elements
        
    Returns:
        Best matching element or None
    """
    if not elements or isinstance(elements, dict):
        return None
        
    description_lower = description.lower()
    
    # Direct name matches (highest priority)
    for elem in elements:
        if elem['name'].lower() == description_lower:
            return elem
    
    # Partial name matches
    best_match = None
    best_score = 0
    
    for elem in elements:
        name_lower = elem['name'].lower()
        
        # Check for partial matches
        if description_lower in name_lower or name_lower in description_lower:
            # Score based on confidence and text similarity
            score = elem.get('confidence', 0.5)
            
            # Boost score for better text matches
            if description_lower == name_lower:
                score += 0.5
            elif description_lower in name_lower:
                score += 0.3
            elif name_lower in description_lower:
                score += 0.2
            
            if score > best_score:
                best_score = score
                best_match = elem
    
    if best_match:
        return best_match
    
    # Control type matches
    type_mappings = {
        'button': 'Button',
        'text field': 'Edit',
        'input': 'Edit',
        'textbox': 'Edit',
        'text box': 'Edit',
        'dropdown': 'ComboBox',
        'checkbox': 'CheckBox',
        'radio': 'RadioButton',
        'link': 'Link'
    }
    
    for keyword, control_type in type_mappings.items():
        if keyword in description_lower:
            matching_elements = [e for e in elements if e['control_type'] == control_type]
            if matching_elements:
                # Return the one with highest confidence
                return max(matching_elements, key=lambda x: x.get('confidence', 0))
    
    return None

def main():
    """Main function for command line usage"""
    discovery = None
    
    try:
        if len(sys.argv) > 1:
            action = sys.argv[1]
            
            if action == "discover":
                # Discover all elements
                discovery = UIElementDiscovery(use_ocr=True)
                elements = discovery.discover_elements()
                print(json.dumps(elements, indent=2))
                
            elif action == "summary":
                # Get actionable summary
                discovery = UIElementDiscovery(use_ocr=True)
                elements = discovery.discover_elements()
                if isinstance(elements, list):
                    summary = get_actionable_elements_summary(elements)
                    print(json.dumps(summary, indent=2))
                else:
                    print(json.dumps(elements, indent=2))
                    
            elif action == "find" and len(sys.argv) > 2:
                # Find specific element
                description = " ".join(sys.argv[2:])
                discovery = UIElementDiscovery(use_ocr=True)
                elements = discovery.discover_elements()
                if isinstance(elements, list):
                    found = find_element_by_description(description, elements)
                    if found:
                        print(json.dumps(found, indent=2))
                    else:
                        print(json.dumps({'error': f'Element not found: {description}'}, indent=2))
                else:
                    print(json.dumps(elements, indent=2))
                    
            elif action == "debug":
                # Create debug image showing detected elements
                discovery = UIElementDiscovery(use_ocr=True)
                elements = discovery.discover_elements()
                if isinstance(elements, list):
                    output_path = sys.argv[2] if len(sys.argv) > 2 else "debug_elements.png"
                    discovery.save_debug_image(output_path)
                    print(json.dumps({'status': 'success', 'message': f'Debug image saved to {output_path}', 'elements_found': len(elements)}, indent=2))
                else:
                    print(json.dumps(elements, indent=2))
                    
            elif action == "test":
                # Test the system
                discovery = UIElementDiscovery(use_ocr=True)
                try:
                    screenshot = discovery._capture_screen()
                    if screenshot is not None:
                        print(json.dumps({'status': 'success', 'message': 'Host screen capture working', 'screen_size': f'{screenshot.shape[1]}x{screenshot.shape[0]}'}, indent=2))
                    else:
                        print(json.dumps({'status': 'error', 'message': 'Failed to capture screen'}, indent=2))
                except Exception as e:
                    print(json.dumps({'status': 'error', 'message': str(e)}, indent=2))
                    
            else:
                print(json.dumps({'error': 'Usage: python ui_element_discovery.py [discover|summary|find <description>|debug [output.png]|test]'}, indent=2))
        else:
            # Default: return summary
            discovery = UIElementDiscovery(use_ocr=True)
            elements = discovery.discover_elements()
            if isinstance(elements, list):
                summary = get_actionable_elements_summary(elements)
                print(json.dumps(summary, indent=2))
            else:
                print(json.dumps(elements, indent=2))
                
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(json.dumps({'error': str(e), 'traceback': traceback.format_exc()}, indent=2))

if __name__ == "__main__":
    main() 