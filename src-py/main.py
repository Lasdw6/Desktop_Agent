# src-py/main.py

import base64
import io
import os
import re
import subprocess
import threading
import json
from datetime import datetime

import pyautogui
import regex
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from mss import mss
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from ui_element_discovery import UIElementDiscovery, find_element_by_description, get_actionable_elements_summary
from windows_ui_automation import (
    discover_windows_elements,
    get_windows_actionable_summary,
    find_windows_element_by_description,
)
from web_browser_automation import WebBrowserAutomation, find_web_element_by_description

# Load environment variables from .env file
def load_env():
    # Try multiple locations for .env file
    env_paths = [
        '.env',
        'src-py/.env',
        '../.env',
        './.env',
    ]
    for path in env_paths:
        if os.path.exists(path):
            if load_dotenv(dotenv_path=path):
                print(f"Successfully loaded .env from: {path}")
                return True
    # Try default dotenv load
    if load_dotenv():
        print("Successfully loaded .env using default dotenv()")
        return True
    return False

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = None
if load_env():
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        client = OpenAI(api_key=api_key)

# Global variables
action_logs = []
log_id_counter = 0
automation_state = {
    'goal': '',
    'step_count': 0,
    'completed': False,
    'last_instruction': ''
}

# Add log entry
def add_log(action_type, description, coordinates=None, text_content=None, success=True, error_message=None):
    global log_id_counter
    log_id_counter += 1
    
    log_entry = {
        'id': log_id_counter,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'action_type': action_type,
        'description': description,
        'coordinates': coordinates,
        'text_content': text_content,
        'success': success,
        'error_message': error_message
    }
    
    action_logs.append(log_entry)
    
    # Keep only the last 100 logs
    if len(action_logs) > 100:
        action_logs.pop(0)

# Extract coordinates from instruction text
def extract_coordinates(instruction):
    # Look for patterns like "coordinates (x, y)" or "(x, y)"
    pattern = r'\((\d+),\s*(\d+)\)'
    match = re.search(pattern, instruction)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    
    # Alternative pattern: "at x, y" or "x y"
    pattern2 = r'(?:at\s+)?(\d+)[,\s]+(\d+)'
    match2 = re.search(pattern2, instruction)
    if match2:
        return (int(match2.group(1)), int(match2.group(2)))
    
    return None

# Extract text to type from instruction
def extract_text_to_type(instruction):
    # Look for text in quotes
    quote_match = re.search(r'"([^"]*)"', instruction)
    if quote_match:
        return quote_match.group(1)
    
    # Look for "type" followed by text
    type_match = re.search(r'type\s+(.+)', instruction, re.IGNORECASE)
    if type_match:
        return type_match.group(1).strip()
    
    return None

# Extract element description from instruction
def extract_element_description(instruction):
    # Look for text in quotes
    quote_match = re.search(r'"([^"]*)"', instruction)
    if quote_match:
        return quote_match.group(1)
    
    # Look for "click" followed by text
    click_match = re.search(r'click\s+(.+?)(?:\s+at|$)', instruction, re.IGNORECASE)
    if click_match:
        return click_match.group(1).strip()
    
    return None

# Execute automation action
def execute_automation_action(instruction):
    instruction_lower = instruction.lower()
    
    try:
        # Parse click commands
        if 'click' in instruction_lower:
            coords = extract_coordinates(instruction)
            if coords:
                x, y = coords
                pyautogui.moveTo(x, y)
                pyautogui.click()
                add_log("CLICK", f"Clicked at coordinates ({x}, {y})", (x, y))
                return f"✓ Clicked at coordinates ({x}, {y})"
            else:
                return "Could not extract coordinates from click instruction"
        
        # Parse type commands
        if 'type' in instruction_lower:
            text = extract_text_to_type(instruction)
            if text:
                pyautogui.typewrite(text)
                add_log("TYPE", f"Typed text: {text}", text_content=text)
                return f"✓ Typed: {text}"
            else:
                return "Could not extract text from type instruction"
        
        # Parse key press commands
        if 'press' in instruction_lower:
            if 'enter' in instruction_lower:
                pyautogui.press('enter')
                add_log("KEY_PRESS", "Pressed Enter key")
                return "✓ Pressed Enter"
            elif 'tab' in instruction_lower:
                pyautogui.press('tab')
                add_log("KEY_PRESS", "Pressed Tab key")
                return "✓ Pressed Tab"
            elif 'escape' in instruction_lower:
                pyautogui.press('escape')
                add_log("KEY_PRESS", "Pressed Escape key")
                return "✓ Pressed Escape"
            elif 'space' in instruction_lower:
                pyautogui.press('space')
                add_log("KEY_PRESS", "Pressed Space key")
                return "✓ Pressed Space"
        
        # Parse scroll commands
        if 'scroll' in instruction_lower:
            if 'down' in instruction_lower:
                pyautogui.scroll(-3)
                add_log("SCROLL", "Scrolled down")
                return "✓ Scrolled down"
            elif 'up' in instruction_lower:
                pyautogui.scroll(3)
                add_log("SCROLL", "Scrolled up")
                return "✓ Scrolled up"
        
        return f"ℹ️ Instruction recognized but no action executed: {instruction}"
        
    except Exception as e:
        add_log("ERROR", f"Failed to execute instruction: {instruction}", error_message=str(e), success=False)
        return f"❌ Error executing instruction: {str(e)}"

# --- UI Automation Functions ---

def discover_ui_elements(focus_application=None, method: str = 'auto'):
    """Discover all UI elements.

    method:
      - 'windows': Use Windows UI Automation (uiautomation)
      - 'cv': Use Computer Vision + OCR
      - 'auto': Try Windows UIA first on Windows, fallback to CV
    """
    try:
        if method == 'windows' or (method == 'auto' and os.name == 'nt'):
            elements = discover_windows_elements(app_filter=focus_application)
            # If UIA unavailable or failed, it returns a list with an error dict
            if isinstance(elements, list) and elements and isinstance(elements[0], dict) and elements[0].get('error'):
                # Fallback to CV
                discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.5)
                return discovery.discover_elements(focus_application=focus_application)
            return elements

        # CV mode
        discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.5)
        return discovery.discover_elements(focus_application=focus_application)
    except Exception as e:
        return {"error": f"Failed to discover UI elements: {str(e)}"}

def execute_ui_automation_action(instruction):
    """Execute automation action with UI element awareness"""
    try:
        # First try to find elements
        elements = discover_ui_elements()
        if isinstance(elements, dict) and 'error' in elements:
            return execute_automation_action(instruction)  # Fallback to coordinate-based
        
        instruction_lower = instruction.lower()
        
        # Look for element-based actions
        if "click" in instruction_lower:
            # Try to extract element description
            element_description = extract_element_description(instruction)
            if element_description:
                found_element = find_element_by_description(element_description, elements)
                if found_element:
                    x = found_element['bounding_rect']['center_x']
                    y = found_element['bounding_rect']['center_y']
                    pyautogui.moveTo(x, y)
                    pyautogui.click()
                    add_log("UI_CLICK", f"Clicked '{found_element['name']}' at ({x}, {y})", (x, y))
                    return f"✓ UI-Clicked '{found_element['name']}' at ({x}, {y})"
        
        # Fallback to coordinate-based automation
        return execute_automation_action(instruction)
        
    except Exception as e:
        add_log("UI_ERROR", f"UI automation failed: {instruction}", error_message=str(e), success=False)
        return execute_automation_action(instruction)  # Fallback

# --- Screenshot Functions ---

def take_screenshot():
    """Take a screenshot and return base64 encoded image"""
    try:
        with mss() as sct:
            # Get the primary monitor
            monitor = sct.monitors[1]
            
            # Take screenshot
            screenshot = sct.grab(monitor)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            add_log("SCREENSHOT", "Screenshot captured successfully")
            return img_str
            
    except Exception as e:
        add_log("SCREENSHOT", "Failed to capture screenshot", error_message=str(e), success=False)
        return None

def take_screenshot_with_grid():
    """Take a screenshot with grid overlay and return base64 encoded image"""
    try:
        with mss() as sct:
            # Get the primary monitor
            monitor = sct.monitors[1]
            
            # Take screenshot
            screenshot = sct.grab(monitor)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Add grid overlay
            draw = ImageDraw.Draw(img)
            width, height = img.size
            
            # Grid settings
            grid_size = 75
            
            # Draw grid lines
            for x in range(0, width, grid_size):
                draw.line([(x, 0), (x, height)], fill=(255, 0, 0, 128), width=1)
            for y in range(0, height, grid_size):
                draw.line([(0, y), (width, y)], fill=(255, 0, 0, 128), width=1)
            
            # Add coordinate labels
            try:
                font = ImageFont.truetype("arial.ttf", 10)
            except:
                font = ImageFont.load_default()
            
            for x in range(0, width, grid_size):
                for y in range(0, height, grid_size):
                    if x + 40 < width and y + 15 < height:
                        text = f"({x},{y})"
                        draw.text((x+2, y+2), text, fill=(255, 255, 255), font=font)
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            add_log("SCREENSHOT", "Screenshot with grid captured successfully")
            return img_str
            
    except Exception as e:
        add_log("SCREENSHOT", "Failed to capture screenshot with grid", error_message=str(e), success=False)
        return None

# --- Browser Automation Functions ---

def discover_browser_elements(target_browser=None):
    """Discover browser UI elements using browser-specific automation"""
    try:
        browser_automation = WebBrowserAutomation()
        elements = browser_automation.discover_browser_elements(target_browser)
        return elements
    except Exception as e:
        return {"error": f"Failed to discover browser elements: {str(e)}"}

def execute_browser_automation_action(instruction):
    """Execute browser automation action"""
    try:
        # For now, use the same UI automation approach
        return execute_ui_automation_action(instruction)
    except Exception as e:
        add_log("BROWSER_ERROR", f"Browser automation failed: {instruction}", error_message=str(e), success=False)
        return f"❌ Browser automation error: {str(e)}"

# --- Chat Functions ---

def chat_with_gpt(message):
    """Chat with GPT using OpenAI API"""
    if not client:
        return "OpenAI client not initialized. Please check your API key."
    
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano-2025-08-07", # DO NOT CHANGE THIS MODEL
            messages=[
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        add_log("CHAT_ERROR", f"Chat failed: {message}", error_message=str(e), success=False)
        return f"Error: {str(e)}"

def chat_with_vision(message, image_data):
    """Chat with GPT Vision using OpenAI API"""
    if not client:
        return "OpenAI client not initialized. Please check your API key."
    
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano-2025-08-07", # DO NOT CHANGE THIS MODEL
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_completion_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        add_log("VISION_ERROR", f"Vision chat failed: {message}", error_message=str(e), success=False)
        return f"Error: {str(e)}"

# --- Flask Routes ---

@app.route("/", methods=['GET'])
def home():
    return jsonify({
        "message": "Desktop Agent Python Backend",
        "version": "2.0.0",
        "features": [
            "Host Screen UI Element Detection",
            "Computer Vision + OCR",
            "Browser Automation",
            "Screenshot Capture",
            "GPT Integration",
            "Action Logging"
        ]
    })

@app.route("/health", methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "openai_configured": client is not None
    })

# --- Screenshot Routes ---

@app.route("/screenshot", methods=['GET'])
def screenshot_route():
    """Take a screenshot"""
    try:
        img_str = take_screenshot()
        if img_str:
            return jsonify({"screenshot": img_str})
        else:
            return jsonify({"error": "Failed to capture screenshot"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/screenshot-with-grid", methods=['GET'])
def screenshot_with_grid_route():
    """Take a screenshot with grid overlay"""
    try:
        img_str = take_screenshot_with_grid()
        if img_str:
            return jsonify({"screenshot": img_str})
        else:
            return jsonify({"error": "Failed to capture screenshot with grid"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Chat Routes ---

@app.route("/chat", methods=['POST'])
def chat_route():
    """Chat with GPT"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        response = chat_with_gpt(message)
        return jsonify({"response": response})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/chat-vision", methods=['POST'])
def chat_vision_route():
    """Chat with GPT Vision"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        image_data = data.get('image_data', '')
        
        if not message or not image_data:
            return jsonify({"error": "Message and image_data are required"}), 400
        
        response = chat_with_vision(message, image_data)
        return jsonify({"response": response})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Automation Routes ---

@app.route("/execute-action", methods=['POST'])
def execute_action_route():
    """Execute automation action"""
    try:
        data = request.get_json()
        instruction = data.get('instruction', '')
        
        if not instruction:
            return jsonify({"error": "Instruction is required"}), 400
        
        result = execute_ui_automation_action(instruction)
        return jsonify({"result": result})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- UI Automation Routes ---

@app.route("/discover-ui-elements", methods=['GET'])
def discover_ui_elements_route():
    """Discover all UI elements"""
    try:
        target_app = request.args.get('app', None)
        elements = discover_ui_elements(focus_application=target_app)
        return jsonify(elements)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/ui-summary", methods=['GET'])
def ui_summary_route():
    """Get UI elements summary. Choose method with ?method=windows|cv|auto"""
    try:
        target_app = request.args.get('app', None)
        method = request.args.get('method', 'auto').lower()
        elements = discover_ui_elements(focus_application=target_app, method=method)
        if isinstance(elements, list):
            if method == 'windows' or (method == 'auto' and os.name == 'nt'):
                summary = get_windows_actionable_summary(elements)
            else:
                summary = get_actionable_elements_summary(elements)
            return jsonify(summary)
        else:
            return jsonify(elements)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/find-ui-element", methods=['POST'])
def find_ui_element_route():
    """Find UI element by description"""
    try:
        data = request.get_json()
        description = data.get('description', '')
        method = (data.get('method') or 'auto').lower()
        
        if not description:
            return jsonify({"error": "Description is required"}), 400
        
        elements = discover_ui_elements(method=method)
        if isinstance(elements, list):
            if method == 'windows' or (method == 'auto' and os.name == 'nt'):
                found = find_windows_element_by_description(description, elements)
            else:
                found = find_element_by_description(description, elements)
            if found:
                return jsonify(found)
            else:
                return jsonify({"error": f"Element not found: {description}"}), 404
        else:
            return jsonify(elements), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Windows-specific UIA routes ---

@app.route('/windows-ui-elements', methods=['GET'])
def windows_ui_elements_route():
    try:
        target_app = request.args.get('app', None)
        elements = discover_windows_elements(app_filter=target_app)
        return jsonify(elements)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/windows-ui-summary', methods=['GET'])
def windows_ui_summary_route():
    try:
        target_app = request.args.get('app', None)
        elements = discover_windows_elements(app_filter=target_app)
        if isinstance(elements, list):
            return jsonify(get_windows_actionable_summary(elements))
        return jsonify(elements)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Browser Automation Routes ---

@app.route("/discover-browser-elements", methods=['GET'])
def discover_browser_elements_route():
    """Discover browser UI elements"""
    try:
        target_browser = request.args.get('browser', None)
        elements = discover_browser_elements(target_browser)
        return jsonify(elements)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/browser-summary", methods=['GET'])
def browser_summary_route():
    """Get browser elements summary"""
    try:
        target_browser = request.args.get('browser', None)
        elements = discover_browser_elements(target_browser)
        return jsonify(elements)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/find-browser-element", methods=['POST'])
def find_browser_element_route():
    """Find browser element by description"""
    try:
        data = request.get_json()
        description = data.get('description', '')
        target_browser = data.get('browser', None)
        
        if not description:
            return jsonify({"error": "Description is required"}), 400
        
        elements = discover_browser_elements(target_browser)
        if isinstance(elements, dict) and 'error' not in elements:
            found = find_web_element_by_description(description, elements)
            if found:
                return jsonify(found)
            else:
                return jsonify({"error": f"Element not found: {description}"}), 404
        else:
            return jsonify(elements), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Action Logging Routes ---

@app.route("/action-logs", methods=['GET'])
def get_action_logs_route():
    """Get action logs"""
    try:
        return jsonify(action_logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear-logs", methods=['POST'])
def clear_logs_route():
    """Clear action logs"""
    try:
        global action_logs, log_id_counter
        action_logs = []
        log_id_counter = 0
        return jsonify({"message": "Action logs cleared successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/log-action", methods=['POST'])
def log_action_route():
    """Log manual action"""
    try:
        data = request.get_json()
        action_type = data.get('action_type', '')
        description = data.get('description', '')
        coordinates = data.get('coordinates', None)
        text_content = data.get('text_content', None)
        
        if not action_type or not description:
            return jsonify({"error": "action_type and description are required"}), 400
        
        add_log(action_type, description, coordinates, text_content)
        return jsonify({"message": "Action logged successfully"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Test Routes ---

@app.route("/test-host-screen", methods=['GET'])
def test_host_screen_route():
    """Test host screen UI detection setup"""
    try:
        discovery = UIElementDiscovery(use_ocr=True, confidence_threshold=0.5)
        screenshot = discovery._capture_screen()
        if screenshot is not None:
            screen_size = f"{screenshot.shape[1]}x{screenshot.shape[0]}"
            return jsonify({"status": "success", "message": "Host screen capture working", "screen_size": screen_size})
        else:
            return jsonify({"status": "error", "message": "Failed to capture host screen"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    print("Starting Desktop Agent Python Backend with Host Screen Detection...")
    print("Available endpoints:")
    print("  GET  /                     - Home")
    print("  GET  /health               - Health check")
    print("  GET  /screenshot           - Take screenshot")
    print("  GET  /screenshot-with-grid - Take screenshot with grid")
    print("  POST /chat                 - Chat with GPT")
    print("  POST /chat-vision          - Chat with GPT Vision")
    print("  POST /execute-action       - Execute automation action")
    print("  GET  /discover-ui-elements - Discover UI elements")
    print("  GET  /ui-summary           - Get UI elements summary")
    print("  POST /find-ui-element      - Find UI element by description")
    print("  GET  /test-host-screen     - Test host screen detection")
    print()
    # Run without the debug reloader to avoid mid-request restarts
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)