# Web Browser Automation - Specialized for Chrome and other browsers
# Handles both browser UI controls and web page content

import json
import sys
# Ensure UTF-8 encoding on Windows to print emojis
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import traceback
import time
import re
from typing import List, Dict, Any, Optional
import uiautomation as auto

class WebBrowserElement:
    """Represents a web browser UI element"""
    def __init__(self, element: auto.Control, element_type: str = "unknown"):
        self.element = element
        self.name = element.Name
        self.control_type = element.ControlTypeName
        self.automation_id = element.AutomationId
        self.class_name = element.ClassName
        self.bounding_rect = element.BoundingRectangle
        self.is_enabled = element.IsEnabled
        self.is_visible = element.IsOffscreen == False
        self.help_text = getattr(element, 'HelpText', '')
        self.access_key = getattr(element, 'AccessKey', '')
        self.element_type = element_type  # 'browser_control', 'web_content', 'tab', etc.
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'control_type': self.control_type,
            'automation_id': self.automation_id,
            'class_name': self.class_name,
            'element_type': self.element_type,
            'bounding_rect': {
                'left': self.bounding_rect.left,
                'top': self.bounding_rect.top,
                'right': self.bounding_rect.right,
                'bottom': self.bounding_rect.bottom,
                'width': self.bounding_rect.right - self.bounding_rect.left,
                'height': self.bounding_rect.bottom - self.bounding_rect.top,
                'center_x': (self.bounding_rect.left + self.bounding_rect.right) // 2,
                'center_y': (self.bounding_rect.top + self.bounding_rect.bottom) // 2,
            },
            'is_enabled': self.is_enabled,
            'is_visible': self.is_visible,
            'help_text': self.help_text,
            'access_key': self.access_key,
            'clickable': self.is_clickable(),
            'typable': self.is_typable(),
            'url_related': self.is_url_related(),
        }
    
    def is_clickable(self) -> bool:
        """Determine if element is clickable"""
        clickable_types = [
            'Button', 'Hyperlink', 'MenuItem', 'TabItem', 'ListItem',
            'CheckBox', 'RadioButton', 'Image', 'Text', 'Document'
        ]
        
        # Web-specific clickable patterns
        web_clickable_keywords = [
            'click', 'button', 'link', 'tab', 'menu', 'back', 'forward',
            'refresh', 'reload', 'bookmark', 'home', 'search', 'go',
            'submit', 'login', 'signin', 'signup', 'download', 'upload'
        ]
        
        name_lower = self.name.lower()
        return (
            self.control_type in clickable_types or
            any(keyword in name_lower for keyword in web_clickable_keywords) or
            len(self.name.strip()) > 0
        )
    
    def is_typable(self) -> bool:
        """Determine if element accepts text input"""
        typable_types = ['Edit', 'Document', 'ComboBox']
        
        # Web-specific typable patterns
        web_typable_keywords = [
            'search', 'address', 'url', 'input', 'text', 'field',
            'username', 'password', 'email', 'query', 'type'
        ]
        
        name_lower = self.name.lower()
        return (
            self.control_type in typable_types or
            any(keyword in name_lower for keyword in web_typable_keywords)
        )
    
    def is_url_related(self) -> bool:
        """Determine if element is related to URL/navigation"""
        url_keywords = [
            'address', 'url', 'location', 'back', 'forward', 'refresh',
            'reload', 'home', 'bookmark', 'history', 'tab'
        ]
        
        name_lower = self.name.lower()
        automation_id_lower = self.automation_id.lower()
        
        return any(keyword in name_lower or keyword in automation_id_lower 
                  for keyword in url_keywords)

class WebBrowserAutomation:
    """Main class for web browser automation"""
    
    def __init__(self, max_depth: int = 15):
        self.max_depth = max_depth
        self.found_elements: List[WebBrowserElement] = []
        
    def find_browser_windows(self) -> List[auto.Control]:
        """Find all open browser windows"""
        browser_patterns = [
            ('chrome', 'Chrome_WidgetWin_1'),
            ('firefox', 'MozillaWindowClass'),
            ('edge', 'ApplicationFrameWindow'),
            ('safari', 'SafariWindow'),
            ('opera', 'OperaWindowClass'),
        ]
        
        browser_windows = []
        root = auto.GetRootControl()
        
        for window in root.GetChildren():
            try:
                if window.IsOffscreen or not window.IsEnabled:
                    continue
                    
                window_name = window.Name.lower()
                class_name = window.ClassName.lower()
                
                # Check if it's a browser window
                is_browser = False
                for browser_name, browser_class in browser_patterns:
                    if (browser_name in window_name and 
                        not any(exclude in window_name for exclude in ['cursor', 'vs code', 'visual studio'])):
                        is_browser = True
                        break
                    elif browser_class.lower() in class_name:
                        is_browser = True  
                        break
                
                # Additional check for common browser indicators
                if not is_browser:
                    browser_keywords = ['chrome', 'firefox', 'edge', 'safari', 'opera']
                    exclude_keywords = ['cursor', 'vs code', 'visual studio', 'notepad', 'calculator', 'spotify']
                    
                    has_browser_keyword = any(keyword in window_name for keyword in browser_keywords)
                    has_exclude_keyword = any(keyword in window_name for keyword in exclude_keywords)
                    
                    if has_browser_keyword and not has_exclude_keyword:
                        is_browser = True
                
                if is_browser:
                    browser_windows.append(window)
                        
            except Exception:
                continue
                
        return browser_windows
    
    def discover_browser_elements(self, target_browser: str = None) -> Dict[str, Any]:
        """
        Discover browser elements with categorization
        
        Args:
            target_browser: Specific browser to target ('chrome', 'firefox', etc.)
        """
        try:
            browser_windows = self.find_browser_windows()
            
            if target_browser:
                # Filter for specific browser
                browser_windows = [w for w in browser_windows 
                                 if target_browser.lower() in w.Name.lower()]
            
            if not browser_windows:
                return {'error': f'No browser windows found' + 
                       (f' for {target_browser}' if target_browser else '')}
            
            self.found_elements = []
            
            for browser_window in browser_windows:
                try:
                    self._analyze_browser_window(browser_window)
                except Exception as e:
                    print(f"Error analyzing browser window: {e}")
                    continue
            
            # Categorize and return elements
            return self._categorize_elements()
            
        except Exception as e:
            return {'error': f'Failed to discover browser elements: {str(e)}'}
    
    def _analyze_browser_window(self, browser_window: auto.Control):
        """Analyze a single browser window"""
        try:
            # Add the browser window itself
            browser_elem = WebBrowserElement(browser_window, 'browser_window')
            self.found_elements.append(browser_elem)
            
            # Look for browser controls (tabs, address bar, buttons)
            self._find_browser_controls(browser_window)
            
            # Look for web page content
            self._find_web_content(browser_window)
            
        except Exception as e:
            print(f"Error in browser window analysis: {e}")
    
    def _find_browser_controls(self, browser_window: auto.Control):
        """Find browser UI controls (tabs, address bar, navigation buttons)"""
        try:
            # Common browser control patterns
            control_patterns = {
                'tab': ['tab', 'TabItem'],
                'address_bar': ['address', 'url', 'location', 'Edit'],
                'navigation': ['back', 'forward', 'refresh', 'reload', 'home'],
                'menu': ['menu', 'MenuBar', 'ToolBar'],
                'bookmark': ['bookmark', 'favorite']
            }
            
            self._traverse_for_controls(browser_window, control_patterns, 0)
            
        except Exception as e:
            print(f"Error finding browser controls: {e}")
    
    def _find_web_content(self, browser_window: auto.Control):
        """Find elements within web page content"""
        try:
            # Look for document/content areas  
            documents = []
            panes = []
            try:
                # Search for documents and panes within the browser window
                for child in browser_window.GetChildren():
                    if child.ControlType == auto.ControlType.DocumentControl:
                        documents.append(child)
                    elif child.ControlType == auto.ControlType.PaneControl:
                        panes.append(child)
            except Exception:
                pass
            
            for doc in documents + panes:
                if self._is_web_content_area(doc):
                    self._traverse_web_content(doc, 0)
                    
        except Exception as e:
            print(f"Error finding web content: {e}")
    
    def _traverse_for_controls(self, element: auto.Control, patterns: Dict, depth: int):
        """Traverse looking for specific browser control patterns, going deeper."""
        if depth > 8:  # Increased depth for browser controls
            return
            
        try:
            for child in element.GetChildren():
                try:
                    # For browser chrome (UI), we check all elements, not just enabled/onscreen ones
                    # as the hierarchy can contain disabled containers.
                    element_type = self._classify_browser_element(child, patterns)
                    if element_type != 'unknown':
                        # Avoid duplicates based on element properties
                        is_duplicate = False
                        for e in self.found_elements:
                            if e.element.BoundingRectangle == child.BoundingRectangle and e.name == child.Name and e.control_type == child.ControlTypeName:
                                is_duplicate = True
                                break
                        if not is_duplicate:
                            web_elem = WebBrowserElement(child, element_type)
                            self.found_elements.append(web_elem)
                    
                    # Always traverse deeper, because containers might not be classified 
                    # but could hold important controls.
                    self._traverse_for_controls(child, patterns, depth + 1)
                except Exception:
                    # Some elements might not be accessible. Continue with the next sibling.
                    continue
        except Exception:
            # It might not be possible to get children of some elements.
            pass
    
    def _traverse_web_content(self, element: auto.Control, depth: int):
        """Traverse web page content areas"""
        if depth > self.max_depth:
            return
            
        try:
            # Check if this element is interesting web content
            if self._is_interesting_web_element(element):
                web_elem = WebBrowserElement(element, 'web_content')
                self.found_elements.append(web_elem)
            
            # Continue traversing
            for child in element.GetChildren():
                self._traverse_web_content(child, depth + 1)
                
        except Exception:
            pass
    
    def _classify_browser_element(self, element: auto.Control, patterns: Dict) -> str:
        """Classify browser element based on patterns"""
        try:
            name = element.Name.lower()
            control_type = element.ControlTypeName
            automation_id = element.AutomationId.lower()
            class_name = getattr(element, 'ClassName', '').lower()
            
            # High priority patterns for reliability
            if control_type == 'TabItem':
                return 'tab'
            if control_type == 'Button':
                nav_indicators = ['back', 'forward', 'refresh', 'reload', 'home', 'stop']
                if any(indicator in name for indicator in nav_indicators):
                    return 'navigation'
            if control_type == 'Edit' and 'address and search bar' in name:
                return 'address_bar'
            if control_type == 'PaneControl' and 'address and search bar' in name:
                return 'address_bar' # The container can also be the address bar

            # General pattern matching from dictionary
            for element_type, keywords in patterns.items():
                for keyword in keywords:
                    # Match by keyword in name, automationId, or class name, or match by control type directly
                    if (keyword and keyword in name) or \
                       (keyword and keyword in automation_id) or \
                       (keyword and keyword in class_name) or \
                       (keyword == control_type):
                        return element_type
            
            return 'unknown'
        except Exception:
            return 'unknown'
    
    def _is_web_content_area(self, element: auto.Control) -> bool:
        """Determine if element is a web content area"""
        try:
            # Look for characteristics of web content areas
            name = element.Name.lower()
            class_name = element.ClassName.lower()
            
            web_content_indicators = [
                'content', 'document', 'webpage', 'frame', 'webview',
                'chrome_rendererwidget', 'internet explorer_server'
            ]
            
            return any(indicator in name or indicator in class_name 
                      for indicator in web_content_indicators)
                      
        except Exception:
            return False
    
    def _is_interesting_web_element(self, element: auto.Control) -> bool:
        """Determine if web element is worth including"""
        try:
            if not element.IsEnabled or element.IsOffscreen:
                return False
            
            # Web-specific interesting elements
            interesting_types = [
                'Button', 'Edit', 'Hyperlink', 'Image', 'Text',
                'CheckBox', 'RadioButton', 'ComboBox', 'ListItem'
            ]
            
            interesting_keywords = [
                'button', 'link', 'input', 'search', 'submit', 'click',
                'login', 'signup', 'menu', 'nav', 'header', 'footer'
            ]
            
            name = element.Name.lower()
            has_name = bool(element.Name.strip())
            is_interesting_type = element.ControlTypeName in interesting_types
            has_interesting_keyword = any(keyword in name for keyword in interesting_keywords)
            
            # Check size (skip very small elements)
            try:
                rect = element.BoundingRectangle
                if rect.right - rect.left < 10 or rect.bottom - rect.top < 10:
                    return False
            except:
                pass
            
            return has_name or is_interesting_type or has_interesting_keyword
            
        except Exception:
            return False
    
    def _categorize_elements(self) -> Dict[str, Any]:
        """Categorize found elements for easier use"""
        categorized = {
            'total_elements': len(self.found_elements),
            'browser_windows': [],
            'tabs': [],
            'address_bars': [],
            'navigation_buttons': [],
            'web_content': [],
            'clickable_elements': [],
            'typable_elements': []
        }
        
        for elem_obj in self.found_elements:
            elem_dict = elem_obj.to_dict()
            
            # Categorize by type
            if elem_obj.element_type == 'browser_window':
                categorized['browser_windows'].append(elem_dict)
            elif elem_obj.element_type == 'tab':
                categorized['tabs'].append(elem_dict)
            elif elem_obj.element_type == 'address_bar':
                categorized['address_bars'].append(elem_dict)
            elif elem_obj.element_type == 'navigation':
                categorized['navigation_buttons'].append(elem_dict)
            elif elem_obj.element_type == 'web_content':
                categorized['web_content'].append(elem_dict)
            
            # Also categorize by capability
            if elem_obj.is_clickable():
                categorized['clickable_elements'].append({
                    'name': elem_obj.name,
                    'type': elem_obj.control_type,
                    'element_type': elem_obj.element_type,
                    'center': (elem_dict['bounding_rect']['center_x'], 
                              elem_dict['bounding_rect']['center_y']),
                    'description': f"{elem_obj.control_type}: '{elem_obj.name}' ({elem_obj.element_type})"
                })
            
            if elem_obj.is_typable():
                categorized['typable_elements'].append({
                    'name': elem_obj.name or f"{elem_obj.control_type} field",
                    'type': elem_obj.control_type,
                    'element_type': elem_obj.element_type,
                    'center': (elem_dict['bounding_rect']['center_x'], 
                              elem_dict['bounding_rect']['center_y']),
                    'description': f"{elem_obj.control_type}: '{elem_obj.name or 'Input field'}' ({elem_obj.element_type})"
                })
        
        # Add counts
        categorized.update({
            'clickable_count': len(categorized['clickable_elements']),
            'typable_count': len(categorized['typable_elements']),
            'tabs_count': len(categorized['tabs']),
            'web_content_count': len(categorized['web_content'])
        })
        
        return categorized

def find_web_element_by_description(description: str, elements: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find web element by natural language description"""
    description_lower = description.lower()
    
    # Search in all clickable and typable elements
    all_elements = elements.get('clickable_elements', []) + elements.get('typable_elements', [])
    
    # Direct name matches
    for elem in all_elements:
        if elem['name'].lower() == description_lower:
            return elem
    
    # Partial name matches
    for elem in all_elements:
        if description_lower in elem['name'].lower() or elem['name'].lower() in description_lower:
            return elem
    
    # Web-specific matches
    web_mappings = {
        'address bar': 'address_bar',
        'url bar': 'address_bar', 
        'search bar': 'address_bar',
        'tab': 'tab',
        'back button': 'navigation',
        'forward button': 'navigation',
        'refresh': 'navigation',
        'home': 'navigation'
    }
    
    for keyword, element_type in web_mappings.items():
        if keyword in description_lower:
            matching_elements = [e for e in all_elements if e['element_type'] == element_type]
            if matching_elements:
                return matching_elements[0]
    
    return None

def get_browser_action_summary(elements: Dict[str, Any]) -> str:
    """Create a summary for GPT with browser-specific context"""
    summary = f"""🌐 WEB BROWSER AUTOMATION CONTEXT:

BROWSER WINDOWS ({len(elements.get('browser_windows', []))})"""
    
    for browser in elements.get('browser_windows', [])[:2]:
        summary += f"\n• {browser['name']}"
    
    if elements.get('tabs'):
        summary += f"\n\nOPEN TABS ({len(elements['tabs'])}):"
        for tab in elements['tabs'][:5]:
            summary += f"\n• Tab: '{tab['name']}'"
    
    if elements.get('address_bars'):
        summary += f"\n\nADDRESS/SEARCH BARS ({len(elements['address_bars'])}):"
        for bar in elements['address_bars'][:2]:
            center = bar['bounding_rect']['center_x'], bar['bounding_rect']['center_y']
            summary += f"\n• {bar['name']} at {center}"
    
    if elements.get('navigation_buttons'):
        summary += f"\n\nNAVIGATION CONTROLS ({len(elements['navigation_buttons'])}):"
        for nav in elements['navigation_buttons'][:5]:
            center = nav['bounding_rect']['center_x'], nav['bounding_rect']['center_y']
            summary += f"\n• {nav['name']} at {center}"
    
    summary += f"\n\nWEB PAGE ELEMENTS ({elements.get('web_content_count', 0)}):"
    for content in elements.get('web_content', [])[:5]:
        center = content['bounding_rect']['center_x'], content['bounding_rect']['center_y']
        summary += f"\n• {content['control_type']}: '{content['name']}' at {center}"
    
    summary += f"\n\n🎯 RECOMMENDED BROWSER ACTIONS:\n"
    summary += "• 'Type \"google.com\" in the address bar'\n"
    summary += "• 'Click the \"Search\" button'\n" 
    summary += "• 'Click the \"Back\" button'\n"
    summary += "• 'Open new tab'\n"
    summary += "• 'Click the link \"Home\"'"
    
    return summary

def main():
    """Main function for command line usage"""
    if len(sys.argv) > 1:
        action = sys.argv[1]
        
        browser_automation = WebBrowserAutomation()
        
        if action == "discover":
            # Discover all browser elements
            target_browser = sys.argv[2] if len(sys.argv) > 2 else None
            elements = browser_automation.discover_browser_elements(target_browser)
            print(json.dumps(elements, indent=2))
            
        elif action == "summary":
            # Get browser-specific summary
            target_browser = sys.argv[2] if len(sys.argv) > 2 else None
            elements = browser_automation.discover_browser_elements(target_browser)
            if isinstance(elements, dict) and 'error' not in elements:
                summary = get_browser_action_summary(elements)
                print(summary)
            else:
                print(json.dumps(elements, indent=2))
                
        elif action == "find" and len(sys.argv) > 2:
            # Find specific browser element
            description = " ".join(sys.argv[2:])
            elements = browser_automation.discover_browser_elements()
            if isinstance(elements, dict) and 'error' not in elements:
                found = find_web_element_by_description(description, elements)
                if found:
                    print(json.dumps(found, indent=2))
                else:
                    print(json.dumps({'error': f'Browser element not found: {description}'}, indent=2))
            else:
                print(json.dumps(elements, indent=2))
                
        elif action == "chrome":
            # Chrome-specific discovery
            elements = browser_automation.discover_browser_elements('chrome')
            print(json.dumps(elements, indent=2))
            
        else:
            print(json.dumps({
                'error': 'Usage: python web_browser_automation.py [discover|summary|find <description>|chrome] [browser_name]'
            }, indent=2))
    else:
        # Default: return browser summary
        browser_automation = WebBrowserAutomation()
        elements = browser_automation.discover_browser_elements()
        if isinstance(elements, dict) and 'error' not in elements:
            summary = get_browser_action_summary(elements)
            print(summary)
        else:
            print(json.dumps(elements, indent=2))

if __name__ == "__main__":
    main() 