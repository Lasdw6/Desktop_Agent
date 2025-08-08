// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use chrono::{DateTime, Utc};
use dotenvy::dotenv;
use enigo::{Button, Direction, Enigo, Key, Keyboard, Mouse, Settings};
use image::{ImageFormat, Rgba, RgbaImage};
use regex;
use reqwest::Client;
use scrap::{Capturer, Display};
use serde::{Deserialize, Serialize};
use std::env;
use std::io::Cursor;
use std::process::Command;
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::Duration;
use uiautomation::UIAutomation;

// Load environment variables from .env file
fn load_env() -> Result<(), String> {
    // Try multiple locations for .env file
    let env_paths = vec![
        ".env",           // Current directory (src-tauri/.env when running from src-tauri)
        "src-tauri/.env", // From project root
        "../.env",        // Parent directory
        "./.env",         // Explicit current directory
    ];

    let mut last_error = String::new();

    for path in env_paths {
        match dotenvy::from_path(path) {
            Ok(_) => {
                println!("Successfully loaded .env from: {}", path);
                return Ok(());
            }
            Err(e) => {
                last_error = format!("Failed to load {}: {}", path, e);
                println!("{}", last_error);
            }
        }
    }

    // If all paths failed, try the default dotenv() which looks in current directory
    if let Ok(_) = dotenv() {
        println!("Successfully loaded .env using default dotenv()");
        return Ok(());
    }

    Err(format!(
        "Could not find .env file in any location. Last error: {}",
        last_error
    ))
}

#[derive(Serialize, Deserialize, Debug)]
struct ChatMessage {
    role: String,
    content: String,
}

#[derive(Serialize, Debug)]
struct ChatRequest<'a> {
    model: &'a str,
    messages: Vec<ChatMessage>,
}

#[derive(Deserialize, Debug)]
struct ChatResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize, Debug)]
struct Choice {
    message: ChatMessage,
}

#[derive(Serialize, Deserialize, Debug)]
#[serde(untagged)]
enum MessageContent {
    Text(String),
    ContentArray(Vec<ContentPart>),
}

#[derive(Serialize, Deserialize, Debug)]
struct VisionMessage {
    role: String,
    content: Vec<ContentPart>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ContentPart {
    #[serde(rename = "type")]
    content_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    image_url: Option<ImageUrl>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ImageUrl {
    url: String,
    detail: String,
}

#[derive(Serialize, Debug)]
struct VisionRequest<'a> {
    model: &'a str,
    messages: Vec<VisionMessage>,
    max_tokens: u32,
}

#[derive(Deserialize, Debug)]
struct VisionResponse {
    choices: Vec<VisionChoice>,
}

#[derive(Deserialize, Debug)]
struct VisionChoice {
    message: VisionResponseMessage,
}

#[derive(Deserialize, Debug)]
struct VisionResponseMessage {
    role: String,
    content: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct AutomationState {
    goal: String,
    step_count: u32,
    completed: bool,
    last_instruction: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct AutomationResponse {
    instruction: String,
    completed: bool,
    next_action: String, // "click", "type", "scroll", "wait", "done"
    coordinates: Option<(u32, u32)>,
    text_to_type: Option<String>,
    screenshot: Option<String>, // Base64 encoded screenshot
}

#[derive(Serialize, Deserialize, Debug)]
struct UIElement {
    name: String,
    control_type: String,
    automation_id: String,
    class_name: String,
    bounding_rect: BoundingRect,
    is_enabled: bool,
    is_visible: bool,
    help_text: String,
    access_key: String,
    clickable: bool,
    typable: bool,
}

#[derive(Serialize, Deserialize, Debug)]
struct BoundingRect {
    left: i32,
    top: i32,
    right: i32,
    bottom: i32,
    width: i32,
    height: i32,
    center_x: i32,
    center_y: i32,
}

#[derive(Serialize, Deserialize, Debug)]
struct UIElementSummary {
    total_elements: usize,
    clickable_count: usize,
    typable_count: usize,
    clickable_elements: Vec<ElementInfo>,
    typable_elements: Vec<ElementInfo>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ElementInfo {
    name: String,
    #[serde(rename = "type")]
    element_type: String,
    center: (i32, i32),
    description: String,
}

// Action logging system
#[derive(Serialize, Deserialize, Debug, Clone)]
struct ActionLog {
    id: u32,
    timestamp: DateTime<Utc>,
    action_type: String,
    description: String,
    coordinates: Option<(u32, u32)>,
    text_content: Option<String>,
    success: bool,
    error_message: Option<String>,
}

// Global action log storage
static ACTION_LOGS: OnceLock<Mutex<Vec<ActionLog>>> = OnceLock::new();
static LOG_ID_COUNTER: OnceLock<Mutex<u32>> = OnceLock::new();

// Initialize the logging system
fn init_logging() {
    ACTION_LOGS
        .set(Mutex::new(Vec::new()))
        .expect("Failed to initialize action logs");
    LOG_ID_COUNTER
        .set(Mutex::new(0))
        .expect("Failed to initialize log ID counter");
}

// Add a log entry
fn add_log(
    action_type: &str,
    description: &str,
    coordinates: Option<(u32, u32)>,
    text_content: Option<String>,
    success: bool,
    error_message: Option<String>,
) {
    let logs = ACTION_LOGS.get().expect("Action logs not initialized");
    let counter = LOG_ID_COUNTER
        .get()
        .expect("Log ID counter not initialized");

    let mut logs_guard = logs.lock().unwrap();
    let mut counter_guard = counter.lock().unwrap();

    *counter_guard += 1;
    let log_entry = ActionLog {
        id: *counter_guard,
        timestamp: Utc::now(),
        action_type: action_type.to_string(),
        description: description.to_string(),
        coordinates,
        text_content,
        success,
        error_message,
    };

    logs_guard.push(log_entry);

    // Keep only the last 100 logs to prevent memory issues
    if logs_guard.len() > 100 {
        let len = logs_guard.len();
        logs_guard.drain(0..len - 100);
    }
}

// New function for UI automation
#[cfg(windows)]
fn execute_ui_automation(instruction: &str) -> Result<String, String> {
    let instruction_lower = instruction.to_lowercase();

    // Attempt 1: text wrapped in single quotes
    let mut element_name: Option<&str> = None;
    if let Some(start_idx) = instruction.find("'") {
        if let Some(end_rel) = instruction[start_idx + 1..].find("'") {
            element_name = Some(&instruction[start_idx + 1..start_idx + 1 + end_rel]);
        }
    }

    // Attempt 2: take substring between "click" and " at "
    if element_name.is_none() {
        if let Some(click_idx) = instruction_lower.find("click") {
            let after_click = &instruction[click_idx + 5..]; // skip "click"
            let after_click_trim = after_click.trim_start();
            if !after_click_trim.is_empty() {
                let end_idx = after_click_trim
                    .to_lowercase()
                    .find(" at ")
                    .unwrap_or(after_click_trim.len());
                let candidate = after_click_trim[..end_idx].trim();
                if !candidate.is_empty() && !candidate.starts_with("coordinates") {
                    element_name = Some(candidate);
                }
            }
        }
    }

    if let Some(name) = element_name {
        let automation = UIAutomation::new().map_err(|e| e.to_string())?;
        let root = automation.get_root_element().unwrap();
        let matcher = automation
            .create_matcher()
            .from(root)
            .timeout(5000)
            .name(name);

        if let Ok(element) = matcher.find_first() {
            element.click().unwrap();
            let message = format!("✓ Clicked the '{}' element", name);
            add_log("UI_CLICK", &message, None, None, true, None);
            return Ok(message);
        } else {
            // Continue to fallback path by returning Err
        }
    }

    Err("UI Automation action not recognized".to_string())
}

// Parse and execute automation actions
fn execute_automation_action(instruction: &str) -> Result<String, String> {
    // Initialize enigo for automation
    let mut enigo = Enigo::new(&Settings::default())
        .map_err(|e| format!("Failed to initialize automation: {}", e))?;

    let instruction_lower = instruction.to_lowercase();

    // Parse click commands
    if instruction_lower.contains("click") {
        if let Some(coords) = extract_coordinates(instruction) {
            let (x, y) = coords;

            // Move mouse to coordinates
            enigo
                .move_mouse(x as i32, y as i32, enigo::Coordinate::Abs)
                .map_err(|e| format!("Failed to move mouse: {}", e))?;

            // Small delay to ensure movement completes
            thread::sleep(Duration::from_millis(100));

            // Click
            enigo
                .button(Button::Left, Direction::Click)
                .map_err(|e| format!("Failed to click: {}", e))?;

            // Log the action
            add_log(
                "CLICK",
                &format!("Clicked at coordinates ({}, {})", x, y),
                Some((x, y)),
                None,
                true,
                None,
            );

            return Ok(format!(
                "(Coordinate) ✓ Clicked at coordinates ({}, {})",
                x, y
            ));
        } else {
            return Err("Could not extract coordinates from click instruction".to_string());
        }
    }

    // Parse type commands
    if instruction_lower.contains("type") {
        if let Some(text) = extract_text_to_type(instruction) {
            enigo
                .text(&text)
                .map_err(|e| format!("Failed to type text: {}", e))?;

            // Log the action
            add_log(
                "TYPE",
                &format!("Typed text: {}", text),
                None,
                Some(text.clone()),
                true,
                None,
            );

            return Ok(format!("(Coordinate) ✓ Typed: {}", text));
        } else {
            return Err("Could not extract text from type instruction".to_string());
        }
    }

    // Parse key press commands
    if instruction_lower.contains("press") {
        let key_to_press =
            if instruction_lower.contains("enter") || instruction_lower.contains("return") {
                Some((Key::Return, "Enter"))
            } else if instruction_lower.contains("tab") {
                Some((Key::Tab, "Tab"))
            } else if instruction_lower.contains("escape") {
                Some((Key::Escape, "Escape"))
            } else if instruction_lower.contains("space") {
                Some((Key::Space, "Space"))
            } else {
                None
            };

        if let Some((key, key_name)) = key_to_press {
            enigo
                .key(key, Direction::Click)
                .map_err(|e| format!("Failed to press {}: {}", key_name, e))?;

            add_log(
                "KEY_PRESS",
                &format!("Pressed {} key", key_name),
                None,
                None,
                true,
                None,
            );

            return Ok(format!("(Coordinate) ✓ Pressed {}", key_name));
        } else {
            return Err(
                "Unsupported key press command. Supported keys: Enter, Tab, Escape, Space"
                    .to_string(),
            );
        }
    }

    // Parse scroll commands
    if instruction_lower.contains("scroll") {
        let scroll_amount = if instruction_lower.contains("down") {
            -3
        } else {
            3
        };
        enigo
            .scroll(scroll_amount, enigo::Axis::Vertical)
            .map_err(|e| format!("Failed to scroll: {}", e))?;

        add_log(
            "SCROLL",
            &format!("Scrolled {}", if scroll_amount < 0 { "down" } else { "up" }),
            None,
            None,
            true,
            None,
        );

        return Ok(format!(
            "(Coordinate) ✓ Scrolled {}",
            if scroll_amount < 0 { "down" } else { "up" }
        ));
    }

    // If no action was recognized, return the original instruction
    Ok(format!(
        "ℹ️ Instruction recognized but no action executed: {}",
        instruction
    ))
}

// Extract coordinates from instruction text
fn extract_coordinates(instruction: &str) -> Option<(u32, u32)> {
    // Look for patterns like "coordinates (x, y)" or "(x, y)"
    if let Ok(re) = regex::Regex::new(r"\((\d+),\s*(\d+)\)") {
        if let Some(captures) = re.captures(instruction) {
            let x = captures.get(1)?.as_str().parse::<u32>().ok()?;
            let y = captures.get(2)?.as_str().parse::<u32>().ok()?;
            return Some((x, y));
        }
    }

    // Alternative pattern: "at x, y" or "x y"
    if let Ok(re2) = regex::Regex::new(r"(?:at\s+)?(\d+)[,\s]+(\d+)") {
        if let Some(captures) = re2.captures(instruction) {
            let x = captures.get(1)?.as_str().parse::<u32>().ok()?;
            let y = captures.get(2)?.as_str().parse::<u32>().ok()?;
            return Some((x, y));
        }
    }

    None
}

// Extract text to type from instruction
fn extract_text_to_type(instruction: &str) -> Option<String> {
    // Look for text in quotes
    if let Some(start) = instruction.find('"') {
        if let Some(end) = instruction[start + 1..].find('"') {
            return Some(instruction[start + 1..start + 1 + end].to_string());
        }
    }

    // Look for "type" followed by text
    if let Some(type_pos) = instruction.to_lowercase().find("type") {
        let after_type = instruction[type_pos + 4..].trim();
        if !after_type.is_empty() {
            return Some(after_type.to_string());
        }
    }

    None
}

// Function to add grid overlay with coordinates
fn add_grid_overlay(img: &mut RgbaImage) -> Result<(), String> {
    let (width, height) = img.dimensions();
    let grid_size = 75usize;

    // Grid line color (semi-transparent red)
    let line_color = Rgba([255, 0, 0, 128]);
    // Text background color (semi-transparent black)
    let text_bg_color = Rgba([0, 0, 0, 200]);
    // Text color (white)
    let text_color = Rgba([255, 255, 255, 255]);

    // Draw vertical lines
    for x in (0..=width as usize).step_by(grid_size) {
        let x_u32 = x as u32;
        if x_u32 < width {
            for y in 0..height {
                if let Some(pixel) = img.get_pixel_mut_checked(x_u32, y) {
                    // Blend the grid line color with existing pixel
                    *pixel = blend_colors(*pixel, line_color);
                }
            }
        }
    }

    // Draw horizontal lines
    for y in (0..=height as usize).step_by(grid_size) {
        let y_u32 = y as u32;
        if y_u32 < height {
            for x in 0..width {
                if let Some(pixel) = img.get_pixel_mut_checked(x, y_u32) {
                    // Blend the grid line color with existing pixel
                    *pixel = blend_colors(*pixel, line_color);
                }
            }
        }
    }

    // Add coordinate labels at intersections
    for x in (0..=width as usize).step_by(grid_size) {
        for y in (0..=height as usize).step_by(grid_size) {
            let x_u32 = x as u32;
            let y_u32 = y as u32;

            // Skip coordinates that would be too close to edges or go off screen
            if x_u32 >= width - 40 || y_u32 >= height - 15 {
                continue;
            }

            // Show coordinates at every intersection, but skip (0,0) to reduce clutter at top-left
            if x == 0 && y == 0 {
                continue;
            }

            let coord_text = format!("({},{})", x, y);

            // Position text slightly offset from the intersection point
            let text_x = x as i32 + 2;
            let text_y = y as i32 + 2;

            add_text_with_background(img, &coord_text, text_x, text_y, text_color, text_bg_color);
        }
    }

    Ok(())
}

// Helper function to blend two colors
fn blend_colors(base: Rgba<u8>, overlay: Rgba<u8>) -> Rgba<u8> {
    let alpha = overlay[3] as f32 / 255.0;
    let inv_alpha = 1.0 - alpha;

    Rgba([
        (base[0] as f32 * inv_alpha + overlay[0] as f32 * alpha) as u8,
        (base[1] as f32 * inv_alpha + overlay[1] as f32 * alpha) as u8,
        (base[2] as f32 * inv_alpha + overlay[2] as f32 * alpha) as u8,
        255, // Keep full opacity
    ])
}

// Simple text rendering function
fn add_text_with_background(
    img: &mut RgbaImage,
    text: &str,
    x: i32,
    y: i32,
    text_color: Rgba<u8>,
    bg_color: Rgba<u8>,
) {
    let char_width = 6;
    let char_height = 8;

    // Draw background rectangle
    let bg_width = text.len() as i32 * char_width + 2;
    let bg_height = char_height + 2;

    for dy in 0..bg_height {
        for dx in 0..bg_width {
            let px = x + dx - 1;
            let py = y + dy - 1;
            if px >= 0 && py >= 0 {
                if let Some(pixel) = img.get_pixel_mut_checked(px as u32, py as u32) {
                    *pixel = blend_colors(*pixel, bg_color);
                }
            }
        }
    }

    // Simple bitmap font for numbers (very basic)
    let font_data = get_simple_font();

    for (i, ch) in text.chars().enumerate() {
        if let Some(char_bitmap) = font_data.get(&ch) {
            let char_x = x + (i as i32 * char_width);

            for (row, &byte) in char_bitmap.iter().enumerate() {
                for col in 0..char_width {
                    if (byte >> (char_width - 1 - col)) & 1 == 1 {
                        let px = char_x + col;
                        let py = y + row as i32;
                        if px >= 0 && py >= 0 {
                            if let Some(pixel) = img.get_pixel_mut_checked(px as u32, py as u32) {
                                *pixel = text_color;
                            }
                        }
                    }
                }
            }
        }
    }
}

// Simple bitmap font for digits and common characters
fn get_simple_font() -> std::collections::HashMap<char, Vec<u8>> {
    let mut font = std::collections::HashMap::new();

    // Each character is 6x8 pixels, represented as 8 bytes (rows)
    font.insert(
        '0',
        vec![
            0b011100, 0b100010, 0b100010, 0b100010, 0b100010, 0b100010, 0b011100, 0b000000,
        ],
    );
    font.insert(
        '1',
        vec![
            0b001000, 0b011000, 0b001000, 0b001000, 0b001000, 0b001000, 0b011100, 0b000000,
        ],
    );
    font.insert(
        '2',
        vec![
            0b011100, 0b100010, 0b000010, 0b001100, 0b110000, 0b100000, 0b111110, 0b000000,
        ],
    );
    font.insert(
        '3',
        vec![
            0b011100, 0b100010, 0b000010, 0b001100, 0b000010, 0b100010, 0b011100, 0b000000,
        ],
    );
    font.insert(
        '4',
        vec![
            0b000100, 0b001100, 0b010100, 0b100100, 0b111110, 0b000100, 0b000100, 0b000000,
        ],
    );
    font.insert(
        '5',
        vec![
            0b111110, 0b100000, 0b111100, 0b000010, 0b000010, 0b100010, 0b011100, 0b000000,
        ],
    );
    font.insert(
        '6',
        vec![
            0b011100, 0b100010, 0b100000, 0b111100, 0b100010, 0b100010, 0b011100, 0b000000,
        ],
    );
    font.insert(
        '7',
        vec![
            0b111110, 0b000010, 0b000100, 0b001000, 0b010000, 0b010000, 0b010000, 0b000000,
        ],
    );
    font.insert(
        '8',
        vec![
            0b011100, 0b100010, 0b100010, 0b011100, 0b100010, 0b100010, 0b011100, 0b000000,
        ],
    );
    font.insert(
        '9',
        vec![
            0b011100, 0b100010, 0b100010, 0b011110, 0b000010, 0b100010, 0b011100, 0b000000,
        ],
    );
    font.insert(
        ',',
        vec![
            0b000000, 0b000000, 0b000000, 0b000000, 0b000000, 0b001100, 0b001000, 0b010000,
        ],
    );
    font.insert(
        '(',
        vec![
            0b001100, 0b010000, 0b100000, 0b100000, 0b100000, 0b010000, 0b001100, 0b000000,
        ],
    );
    font.insert(
        ')',
        vec![
            0b110000, 0b001000, 0b000100, 0b000100, 0b000100, 0b001000, 0b110000, 0b000000,
        ],
    );

    font
}

// Simplify call_python_ui_discovery to only use Python scripts
fn call_python_ui_discovery(action: &str, args: &[&str]) -> Result<String, String> {
    // Execute Python script directly
    let mut cmd = Command::new("python");
    cmd.arg("../src-py/ui_element_discovery.py").arg(action);
    for arg in args {
        cmd.arg(arg);
    }
    let output = cmd
        .output()
        .map_err(|e| format!("Failed to execute Python script: {}", e))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        // Print and log Python UI discovery stderr
        println!("PY_UI_DISCOVERY_ERROR (action: {}): {}", action, stderr);
        add_log(
            "PY_UI_DISCOVERY_ERROR",
            &format!("Python ui_element_discovery.py {} stderr", action),
            None,
            Some(stderr.clone()),
            false,
            None,
        );
        return Err(format!("Python script failed: {}", stderr));
    }
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    // Print raw Python UI discovery output to console
    println!("PY_UI_DISCOVERY (action: {}): {}", action, stdout);
    // Log the raw Python UI discovery output
    add_log(
        "PY_UI_DISCOVERY",
        &format!("Python ui_element_discovery.py {} output", action),
        None,
        Some(stdout.clone()),
        true,
        None,
    );
    Ok(stdout)
}

// Simplify call_python_browser_automation to only use Python scripts
fn call_python_browser_automation(action: &str, args: &[&str]) -> Result<String, String> {
    // Execute Python script directly
    let mut cmd = Command::new("python");
    cmd.arg("../src-py/web_browser_automation.py").arg(action);
    for arg in args {
        cmd.arg(arg);
    }
    let output = cmd
        .output()
        .map_err(|e| format!("Failed to execute browser automation script: {}", e))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        // Print and log Python browser automation stderr
        println!(
            "PY_BROWSER_AUTOMATION_ERROR (action: {}): {}",
            action, stderr
        );
        add_log(
            "PY_BROWSER_AUTOMATION_ERROR",
            &format!("Python web_browser_automation.py {} stderr", action),
            None,
            Some(stderr.clone()),
            false,
            None,
        );
        return Err(format!("Browser automation script failed: {}", stderr));
    }
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    // Print raw Python browser automation output to console
    println!("PY_BROWSER_AUTOMATION (action: {}): {}", action, stdout);
    // Log the raw Python browser automation output
    add_log(
        "PY_BROWSER_AUTOMATION",
        &format!("Python web_browser_automation.py {} output", action),
        None,
        Some(stdout.clone()),
        true,
        None,
    );
    Ok(stdout)
}

// Call Python host screen UI detection system
fn call_python_host_screen_detection(action: &str, args: &[&str]) -> Result<String, String> {
    // Execute Python script directly
    let mut cmd = Command::new("python");
    cmd.arg("../src-py/ui_element_discovery.py").arg(action);
    for arg in args {
        cmd.arg(arg);
    }
    let output = cmd
        .output()
        .map_err(|e| format!("Failed to execute host screen detection script: {}", e))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        // Print and log Python host screen detection stderr
        println!("PY_HOST_SCREEN_ERROR (action: {}): {}", action, stderr);
        add_log(
            "PY_HOST_SCREEN_ERROR",
            &format!("Python ui_element_discovery.py {} stderr", action),
            None,
            Some(stderr.clone()),
            false,
            None,
        );
        return Err(format!("Host screen detection script failed: {}", stderr));
    }
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    // Print raw Python host screen detection output to console
    println!("PY_HOST_SCREEN (action: {}): {}", action, stdout);
    // Log the raw Python host screen detection output
    add_log(
        "PY_HOST_SCREEN",
        &format!("Python ui_element_discovery.py {} output", action),
        None,
        Some(stdout.clone()),
        true,
        None,
    );
    Ok(stdout)
}

// UI Element Discovery Functions
fn discover_ui_elements() -> Result<Vec<UIElement>, String> {
    let output = call_python_ui_discovery("discover", &[])?;

    let elements: Vec<UIElement> =
        serde_json::from_str(&output).map_err(|e| format!("Failed to parse UI elements: {}", e))?;

    Ok(elements)
}

// Host Screen UI Element Discovery Functions
fn discover_host_screen_elements() -> Result<serde_json::Value, String> {
    let output = call_python_host_screen_detection("discover", &[])?;

    let elements: serde_json::Value = serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse host screen elements: {}", e))?;

    Ok(elements)
}

fn get_host_screen_elements_summary() -> Result<serde_json::Value, String> {
    let output = call_python_host_screen_detection("test-host-screen", &[])?;

    let summary: serde_json::Value = serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse host screen summary: {}", e))?;

    Ok(summary)
}

// Format host screen UI data for LLM prompts
fn format_host_screen_summary(host_screen_data: &serde_json::Value) -> Option<String> {
    if let Some(elements) = host_screen_data.as_array() {
        if elements.is_empty() {
            return None;
        }

        let mut summary = String::from("\n\n🖥️ HOST SCREEN UI ELEMENTS (Computer Vision):\n");

        let clickable_elements: Vec<&serde_json::Value> = elements
            .iter()
            .filter(|elem| {
                elem.get("clickable")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false)
            })
            .collect();

        let typable_elements: Vec<&serde_json::Value> = elements
            .iter()
            .filter(|elem| {
                elem.get("typable")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false)
            })
            .collect();

        if !clickable_elements.is_empty() {
            summary.push_str(&format!(
                "CLICKABLE ELEMENTS ({} total):\n",
                clickable_elements.len()
            ));
            for (i, elem) in clickable_elements.iter().enumerate().take(10) {
                let name = elem
                    .get("name")
                    .and_then(|n| n.as_str())
                    .unwrap_or("Unknown");
                let control_type = elem
                    .get("control_type")
                    .and_then(|ct| ct.as_str())
                    .unwrap_or("Element");
                let confidence = elem
                    .get("confidence")
                    .and_then(|c| c.as_f64())
                    .unwrap_or(0.0);

                if let Some(bounding_rect) = elem.get("bounding_rect") {
                    let center_x = bounding_rect
                        .get("center_x")
                        .and_then(|x| x.as_i64())
                        .unwrap_or(0);
                    let center_y = bounding_rect
                        .get("center_y")
                        .and_then(|y| y.as_i64())
                        .unwrap_or(0);

                    summary.push_str(&format!(
                        "{}. {}: '{}' at ({}, {}) [confidence: {:.2}]\n",
                        i + 1,
                        control_type,
                        name,
                        center_x,
                        center_y,
                        confidence
                    ));
                }
            }
        }

        if !typable_elements.is_empty() {
            summary.push_str(&format!(
                "\nTYPABLE ELEMENTS ({} total):\n",
                typable_elements.len()
            ));
            for (i, elem) in typable_elements.iter().enumerate().take(5) {
                let name = elem
                    .get("name")
                    .and_then(|n| n.as_str())
                    .unwrap_or("Unknown");
                let control_type = elem
                    .get("control_type")
                    .and_then(|ct| ct.as_str())
                    .unwrap_or("Element");
                let confidence = elem
                    .get("confidence")
                    .and_then(|c| c.as_f64())
                    .unwrap_or(0.0);

                if let Some(bounding_rect) = elem.get("bounding_rect") {
                    let center_x = bounding_rect
                        .get("center_x")
                        .and_then(|x| x.as_i64())
                        .unwrap_or(0);
                    let center_y = bounding_rect
                        .get("center_y")
                        .and_then(|y| y.as_i64())
                        .unwrap_or(0);

                    summary.push_str(&format!(
                        "{}. {}: '{}' at ({}, {}) [confidence: {:.2}]\n",
                        i + 1,
                        control_type,
                        name,
                        center_x,
                        center_y,
                        confidence
                    ));
                }
            }
        }

        summary.push_str("\n✨ HOST SCREEN ACTION FORMAT:\n");
        summary
            .push_str("• 'Click the \"[ElementName]\" button' (Computer Vision - HIGH ACCURACY)\n");
        summary.push_str("• 'Type \"text\" in the \"[ElementName]\" field' (For text inputs)\n");
        summary.push_str("• 'Click coordinates (x, y)' (Fallback when element not found)\n\n");

        return Some(summary);
    }

    None
}

fn get_ui_elements_summary() -> Result<UIElementSummary, String> {
    let output = call_python_ui_discovery("summary", &[])?;

    let summary: UIElementSummary =
        serde_json::from_str(&output).map_err(|e| format!("Failed to parse UI summary: {}", e))?;

    Ok(summary)
}

fn find_ui_element_by_description(description: &str) -> Result<Option<UIElement>, String> {
    let output = call_python_ui_discovery("find", &[description])?;

    // Try to parse as a single element first
    if let Ok(element) = serde_json::from_str::<UIElement>(&output) {
        return Ok(Some(element));
    }

    // If that fails, it might be an error response
    let error_response: serde_json::Value = serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse find response: {}", e))?;

    if error_response.get("error").is_some() {
        return Ok(None);
    }

    Err("Unexpected response format".to_string())
}

// Browser Automation Functions
fn discover_browser_elements_rust(
    target_browser: Option<&str>,
) -> Result<serde_json::Value, String> {
    let args = if let Some(browser) = target_browser {
        vec![browser]
    } else {
        vec![]
    };

    let output = call_python_browser_automation("discover", &args)?;

    let elements: serde_json::Value = serde_json::from_str(&output)
        .map_err(|e| format!("Failed to parse browser elements: {}", e))?;

    Ok(elements)
}

fn get_browser_elements_summary_rust(
    target_browser: Option<&str>,
) -> Result<serde_json::Value, String> {
    let args = if let Some(browser) = target_browser {
        vec![browser]
    } else {
        vec![]
    };

    let output = call_python_browser_automation("summary", &args)?;

    // Try to parse as JSON, but handle text summary as well
    if let Ok(json_summary) = serde_json::from_str::<serde_json::Value>(&output) {
        Ok(json_summary)
    } else {
        // If it's a text summary, wrap it in JSON
        Ok(serde_json::json!({"summary": output}))
    }
}

fn find_browser_element_by_description_rust(
    description: &str,
    target_browser: Option<&str>,
) -> Result<Option<serde_json::Value>, String> {
    let mut args = vec![];
    if let Some(browser) = target_browser {
        args.push(browser);
    }
    args.push(description);

    let output = call_python_browser_automation("find", &args)?;

    // Try to parse as a single element first
    if let Ok(element) = serde_json::from_str::<serde_json::Value>(&output) {
        if element.get("error").is_some() {
            return Ok(None);
        }
        return Ok(Some(element));
    }

    Ok(None)
}

// Helper function to format browser summary for the prompt
fn format_browser_summary(browser_info: &serde_json::Value) -> Option<String> {
    if !browser_info.is_object()
        || browser_info.get("total_elements").and_then(|v| v.as_i64()) == Some(0)
    {
        return None;
    }

    let mut summary = String::from("\n\n🌐 WEB BROWSER CONTEXT:\n");

    if let Some(windows) = browser_info
        .get("browser_windows")
        .and_then(|v| v.as_array())
    {
        if !windows.is_empty() {
            summary.push_str(&format!("Found {} browser window(s):\n", windows.len()));
            for window in windows.iter().take(2) {
                // Limit to 2 windows
                if let Some(name) = window.get("name").and_then(|v| v.as_str()) {
                    if !name.to_lowercase().contains("cursor") {
                        summary.push_str(&format!("  - Window: \"{}\"\n", name));
                    }
                }
            }
        }
    }

    if let Some(tabs) = browser_info.get("tabs").and_then(|v| v.as_array()) {
        if !tabs.is_empty() {
            summary.push_str(&format!("\nOpen Tabs ({} total):\n", tabs.len()));
            for tab in tabs.iter().take(5) {
                // Limit to 5 tabs
                if let Some(name) = tab.get("name").and_then(|v| v.as_str()) {
                    if !name.trim().is_empty() {
                        summary.push_str(&format!("  - Tab: \"{}\"\n", name));
                    }
                }
            }
        }
    }

    if let Some(address_bars) = browser_info.get("address_bars").and_then(|v| v.as_array()) {
        if !address_bars.is_empty() {
            summary.push_str("\nAddress Bar(s):\n");
            for bar in address_bars.iter().take(2) {
                if let Some(name) = bar.get("name").and_then(|v| v.as_str()) {
                    let center_x = bar
                        .get("bounding_rect")
                        .and_then(|r| r.get("center_x"))
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0);
                    let center_y = bar
                        .get("bounding_rect")
                        .and_then(|r| r.get("center_y"))
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0);
                    summary.push_str(&format!(
                        "  - \"{}\" at ({}, {})\n",
                        name, center_x, center_y
                    ));
                }
            }
        }
    }

    if let Some(nav_buttons) = browser_info
        .get("navigation_buttons")
        .and_then(|v| v.as_array())
    {
        if !nav_buttons.is_empty() {
            summary.push_str("\nNavigation Buttons:\n");
            for button in nav_buttons.iter().take(4) {
                if let Some(name) = button.get("name").and_then(|v| v.as_str()) {
                    let center_x = button
                        .get("bounding_rect")
                        .and_then(|r| r.get("center_x"))
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0);
                    let center_y = button
                        .get("bounding_rect")
                        .and_then(|r| r.get("center_y"))
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0);
                    summary.push_str(&format!(
                        "  - \"{}\" button at ({}, {})\n",
                        name, center_x, center_y
                    ));
                }
            }
        }
    }

    summary.push_str("\n✨ BROWSER ACTION FORMAT:\n");
    summary.push_str("• 'Type \"cats\" in the \"Address and search bar\"'\n");
    summary.push_str("• 'Click the \"New Tab\" button'\n");
    summary.push_str("• 'Click the \"Back\" button'\n\n");

    Some(summary)
}

fn create_enhanced_automation_prompt(
    goal: &str,
    previous_instruction: Option<&str>,
    step_count: Option<u32>,
    width: u32,
    height: u32,
) -> String {
    // First, try to get browser context using summary (which returns formatted text)
    let browser_context = match get_browser_elements_summary_rust(None) {
        Ok(summary_data) => {
            // Check if it's a text summary wrapped in JSON
            if let Some(summary_text) = summary_data.get("summary").and_then(|s| s.as_str()) {
                if !summary_text.trim().is_empty() && summary_text.contains("ADDRESS") {
                    format!("\n{}\n", summary_text)
                } else {
                    String::new()
                }
            } else {
                // Try to format as structured data if it's JSON
                format_browser_summary(&summary_data).unwrap_or_default()
            }
        }
        Err(_) => String::new(),
    };

    // Try to get host screen UI elements using computer vision
    let host_screen_info = match discover_host_screen_elements() {
        Ok(elements) => format_host_screen_summary(&elements).unwrap_or_default(),
        Err(_) => String::new(),
    };

    // Try to get UI elements summary for desktop apps (Windows UI Automation)
    let ui_info = match get_ui_elements_summary() {
        Ok(summary) => {
            let mut ui_text = format!(
                "\n🎯 DESKTOP APP UI ELEMENTS (Windows UI Automation):\n\nCLICKABLE ELEMENTS ({} total):\n",
                summary.clickable_count
            );

            for (i, elem) in summary.clickable_elements.iter().enumerate().take(10) {
                ui_text.push_str(&format!(
                    "{}. {} at ({}, {})\n",
                    i + 1,
                    elem.description,
                    elem.center.0,
                    elem.center.1
                ));
            }

            if !summary.typable_elements.is_empty() {
                ui_text.push_str(&format!(
                    "\nTYPABLE ELEMENTS ({} total):\n",
                    summary.typable_count
                ));
                for (i, elem) in summary.typable_elements.iter().enumerate().take(5) {
                    ui_text.push_str(&format!(
                        "{}. {} at ({}, {})\n",
                        i + 1,
                        elem.description,
                        elem.center.0,
                        elem.center.1
                    ));
                }
            }

            ui_text.push_str("\n✨ DESKTOP ACTION FORMAT:\n");
            ui_text.push_str("• 'Click the \"[ElementName]\" button' (UI Automation - BEST)\n");
            ui_text.push_str("• 'Click coordinates (x, y)' (Fallback when element not found)\n\n");

            ui_text
        }
        Err(_) => String::new(),
    };

    let combined_context = format!("{}{}{}", browser_context, host_screen_info, ui_info);

    // Example sequence for reference (helps model understand the desired format)
    let example_sequence = r#"EXAMPLE – NAVIGATE TO SATORU GOJO WIKIPEDIA (one action per step):
1. Click the "Address and search bar"
2. Type "https://en.wikipedia.org/wiki/Satoru_Gojo"
3. Press Enter
4. Wait 3 seconds for the page to load
5. If not on the Wikipedia page, click the first search result titled "Satoru Gojo – Wikipedia and so on until the page is goal is completed""#;

    let base_prompt = if let Some(prev_instruction) = previous_instruction {
        format!(
            r#"AUTOMATION TASK CONTINUATION: {}

Previous step #{}: {}

I've taken the previous action. Here's the current screenshot. The screen resolution is {}x{}.
{}
{}
IMPORTANT – ACTION PREFERENCE (read carefully):
1️⃣  BROWSER/UI-ELEMENT ACTIONS – STRONGLY PREFERRED
    • Reference controls by their visible text/role from the context above.
    • Examples: 
      'Click the "New Tab" button'
      'Type "latest news" in the "Address and search bar"'
      'Click the "Save" button'
    • These instructions are the most reliable.

2️⃣  COORDINATE ACTIONS – LAST RESORT
    • Only give grid coordinates when no unique element can be identified.
    • The agent will prefix results with (Coordinate) when this fallback is used.
    • Example: 'Click coordinates (700, 300)'


GRID SYSTEM:
- Grid squares are 75x75 pixels each
- Coordinates are labeled at intersections like (75,75), (150,150), (225,225), etc.

OTHER AVAILABLE ACTIONS:
- KEYBOARD: 'Press [key name]' (Enter, Tab, Escape, Space)
- SCROLL: 'Scroll [direction]' (up, down)

RESPONSE RULES:
1. Give ONE specific action at a time.
2. For element actions, use exact names from the context.
3. For coordinate actions, use exact grid coordinates.
4. If the goal is completed, say 'TASK COMPLETED'.

Analyze the current state and provide the NEXT SINGLE ACTION to continue toward the goal. What should I do next?"#,
            goal,
            step_count.unwrap_or(0),
            prev_instruction,
            width,
            height,
            combined_context,
            example_sequence
        )
    } else {
        format!(
            r#"AUTOMATION TASK: {}

You are an automation assistant that controls computer actions.
I will provide a screenshot with a grid overlay for precise positioning. The screen resolution is {}x{}.
Use the information from the screenshot and the UI context below to determine the next action.
{}
{}
IMPORTANT – ACTION PREFERENCE (read carefully):
1️⃣  BROWSER/UI-ELEMENT ACTIONS – STRONGLY PREFERRED
    • Reference controls by their visible text/role from the context above.
    • Examples: 
      'Click the "New Tab" button'
      'Type "latest news" in the "Address and search bar"'
      'Click the "Save" button'
    • These instructions are the most reliable.

2️⃣  COORDINATE ACTIONS – LAST RESORT
    • Only give grid coordinates when no unique element can be identified.
    • The agent will prefix results with (Coordinate) when this fallback is used.
    • Example: 'Click coordinates (700, 300)'

GRID SYSTEM:
- Grid squares are 75x75 pixels each
- Coordinates are labeled at intersections like (75,75), (150,150), (225,225), etc.

OTHER AVAILABLE ACTIONS:
- KEYBOARD: 'Press [key name]' (Enter, Tab, Escape, Space)
- SCROLL: 'Scroll [direction]' (up, down)

RESPONSE RULES:
1. Give ONE specific action at a time.
2. For element actions, use exact names from the context.
3. For coordinate actions, use exact grid coordinates.
4. If the goal is completed, say 'TASK COMPLETED'.

What is the first action I should take to accomplish this goal?"#,
            goal, width, height, combined_context, example_sequence
        )
    };

    base_prompt
}

// Enhanced automation action execution with UI element awareness
fn extract_multiple_element_names(instruction: &str) -> Vec<String> {
    let mut candidates = Vec::new();
    let instruction_lower = instruction.to_lowercase();

    // 1. High-priority: Extract all quoted strings.
    if let Ok(re) = regex::Regex::new(r#""([^"]+)""#) {
        for cap in re.captures_iter(&instruction_lower) {
            let candidate = cap[1].trim().to_string();
            if !candidate.is_empty() && !candidates.contains(&candidate) {
                candidates.push(candidate);
            }
        }
    }

    // 2. Add known, important element names if they appear in the instruction.
    let known_elements = [
        "address and search bar",
        "address bar",
        "search bar",
        "new tab",
        "back",
        "forward",
        "reload",
        "refresh",
    ];
    for elem in &known_elements {
        if instruction_lower.contains(elem) {
            let candidate = elem.to_string();
            if !candidates.contains(&candidate) {
                candidates.push(candidate);
            }
        }
    }

    candidates
}

fn execute_enhanced_automation_action(instruction: &str) -> Result<String, String> {
    let potential_targets = extract_multiple_element_names(instruction);
    let instruction_lower = instruction.to_lowercase();

    // ---------------------------------------------
    // 1. CLICK handling (element-based preferred)
    // ---------------------------------------------
    if instruction_lower.contains("click") {
        // Try clicking any identified UI / browser element names first.
        for target_name in &potential_targets {
            // Try host screen element (computer vision - highest priority)
            if let Ok(elements) = discover_host_screen_elements() {
                if let Some(elements_array) = elements.as_array() {
                    for element in elements_array {
                        if let Some(element_name) = element.get("name").and_then(|n| n.as_str()) {
                            if element_name
                                .to_lowercase()
                                .contains(&target_name.to_lowercase())
                            {
                                if let Some(bounding_rect) = element.get("bounding_rect") {
                                    if let (Some(x_val), Some(y_val)) = (
                                        bounding_rect.get("center_x").and_then(|v| v.as_i64()),
                                        bounding_rect.get("center_y").and_then(|v| v.as_i64()),
                                    ) {
                                        let (x, y) = (x_val as u32, y_val as u32);
                                        let mut enigo =
                                            Enigo::new(&Settings::default()).map_err(|e| {
                                                format!("Failed to initialize automation: {}", e)
                                            })?;
                                        enigo
                                            .move_mouse(x as i32, y as i32, enigo::Coordinate::Abs)
                                            .map_err(|e| format!("Failed to move mouse: {}", e))?;
                                        thread::sleep(Duration::from_millis(100));
                                        enigo
                                            .button(Button::Left, Direction::Click)
                                            .map_err(|e| format!("Failed to click: {}", e))?;

                                        let log_msg = format!(
                                            "Clicked host screen element '{}' at ({}, {})",
                                            element_name, x, y
                                        );
                                        add_log(
                                            "HOST_SCREEN_CLICK",
                                            &log_msg,
                                            Some((x, y)),
                                            None,
                                            true,
                                            None,
                                        );
                                        return Ok(format!("✓ {}", log_msg));
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Try browser element
            if let Ok(Some(element)) = find_browser_element_by_description_rust(target_name, None) {
                // Try to get coordinates from either format
                let coordinates =
                    if let Some(center_array) = element.get("center").and_then(|c| c.as_array()) {
                        // Format: "center": [960, 576]
                        if center_array.len() >= 2 {
                            let x = center_array[0].as_i64().unwrap_or(0) as u32;
                            let y = center_array[1].as_i64().unwrap_or(0) as u32;
                            Some((x, y))
                        } else {
                            None
                        }
                    } else if let (Some(x_val), Some(y_val)) = (
                        element
                            .get("bounding_rect")
                            .and_then(|r| r.get("center_x"))
                            .and_then(|v| v.as_i64()),
                        element
                            .get("bounding_rect")
                            .and_then(|r| r.get("center_y"))
                            .and_then(|v| v.as_i64()),
                    ) {
                        // Format: "bounding_rect": {"center_x": 960, "center_y": 576}
                        Some((x_val as u32, y_val as u32))
                    } else {
                        None
                    };

                if let Some((x, y)) = coordinates {
                    let mut enigo = Enigo::new(&Settings::default())
                        .map_err(|e| format!("Failed to initialize automation: {}", e))?;
                    enigo
                        .move_mouse(x as i32, y as i32, enigo::Coordinate::Abs)
                        .map_err(|e| format!("Failed to move mouse: {}", e))?;
                    thread::sleep(Duration::from_millis(100));
                    enigo
                        .button(Button::Left, Direction::Click)
                        .map_err(|e| format!("Failed to click: {}", e))?;

                    let found_name = element
                        .get("name")
                        .and_then(|n| n.as_str())
                        .unwrap_or(target_name);
                    let log_msg =
                        format!("Clicked browser element '{}' at ({}, {})", found_name, x, y);
                    add_log("BROWSER_CLICK", &log_msg, Some((x, y)), None, true, None);
                    return Ok(format!("✓ {}", log_msg));
                }
            }

            // Try desktop UI element
            if let Ok(Some(element)) = find_ui_element_by_description(target_name) {
                let (x, y) = (
                    element.bounding_rect.center_x as u32,
                    element.bounding_rect.center_y as u32,
                );
                let mut enigo = Enigo::new(&Settings::default())
                    .map_err(|e| format!("Failed to initialize automation: {}", e))?;
                enigo
                    .move_mouse(x as i32, y as i32, enigo::Coordinate::Abs)
                    .map_err(|e| format!("Failed to move mouse: {}", e))?;
                thread::sleep(Duration::from_millis(100));
                enigo
                    .button(Button::Left, Direction::Click)
                    .map_err(|e| format!("Failed to click: {}", e))?;

                let log_msg = format!("Clicked UI element '{}' at ({}, {})", element.name, x, y);
                add_log("UI_CLICK", &log_msg, Some((x, y)), None, true, None);
                return Ok(format!("✓ {}", log_msg));
            }
        }

        // Fallback – coordinate-based click if coordinates were provided.
        if extract_coordinates(instruction).is_some() {
            return execute_automation_action(instruction);
        }

        // If we couldn't click anything, surface a clear error so the caller can adjust.
        if !potential_targets.is_empty() {
            return Err(format!(
                "Could not find the UI element(s): '{}'. Please try a different description or use coordinates.",
                potential_targets.join("', '")
            ));
        }

        // No recognised element names – fall through to other handlers.
    }

    // ---------------------------------------------
    // 2. TYPE handling
    // ---------------------------------------------
    if instruction_lower.starts_with("type ") || instruction_lower.contains(" type \"") {
        if let Some(text_to_type) = extract_text_to_type(instruction) {
            // Focus field if target provided
            if !potential_targets.is_empty() {
                let target_name = &potential_targets[0];
                if let Ok(Some(element)) =
                    find_browser_element_by_description_rust(target_name, None)
                {
                    // Try to get coordinates from either format
                    let coordinates = if let Some(center_array) =
                        element.get("center").and_then(|c| c.as_array())
                    {
                        // Format: "center": [960, 576]
                        if center_array.len() >= 2 {
                            let x = center_array[0].as_i64().unwrap_or(0) as u32;
                            let y = center_array[1].as_i64().unwrap_or(0) as u32;
                            Some((x, y))
                        } else {
                            None
                        }
                    } else if let (Some(x_val), Some(y_val)) = (
                        element
                            .get("bounding_rect")
                            .and_then(|r| r.get("center_x"))
                            .and_then(|v| v.as_i64()),
                        element
                            .get("bounding_rect")
                            .and_then(|r| r.get("center_y"))
                            .and_then(|v| v.as_i64()),
                    ) {
                        // Format: "bounding_rect": {"center_x": 960, "center_y": 576}
                        Some((x_val as u32, y_val as u32))
                    } else {
                        None
                    };

                    if let Some((x, y)) = coordinates {
                        let mut enigo = Enigo::new(&Settings::default()).unwrap();
                        enigo
                            .move_mouse(x as i32, y as i32, enigo::Coordinate::Abs)
                            .unwrap();
                        enigo.button(Button::Left, Direction::Click).unwrap();
                        thread::sleep(Duration::from_millis(100));
                    }
                } else if let Ok(Some(element)) = find_ui_element_by_description(target_name) {
                    let (x, y) = (
                        element.bounding_rect.center_x as u32,
                        element.bounding_rect.center_y as u32,
                    );
                    let mut enigo = Enigo::new(&Settings::default()).unwrap();
                    enigo
                        .move_mouse(x as i32, y as i32, enigo::Coordinate::Abs)
                        .unwrap();
                    enigo.button(Button::Left, Direction::Click).unwrap();
                    thread::sleep(Duration::from_millis(100));
                }
            }

            // Type the requested text
            let mut enigo = Enigo::new(&Settings::default())
                .map_err(|e| format!("Failed to initialize automation: {}", e))?;
            enigo
                .text(&text_to_type)
                .map_err(|e| format!("Failed to type text: {}", e))?;
            add_log(
                "TYPE",
                &format!("Typed text: {}", text_to_type),
                None,
                Some(text_to_type.clone()),
                true,
                None,
            );
            return Ok(format!("✓ Typed: {}", text_to_type));
        }
    }

    // ---------------------------------------------
    // 3. Other (press / scroll) & generic fallback
    // ---------------------------------------------
    execute_automation_action(instruction)
}

// This function will now return a raw image buffer
async fn capture_screen(window: tauri::Window) -> Result<RgbaImage, String> {
    // Hide the window to capture what's behind it
    window
        .hide()
        .map_err(|e| format!("Failed to hide window: {}", e))?;
    // Give the OS a moment to hide the window before capturing.
    // This duration might need adjustment depending on the OS and system performance.
    thread::sleep(Duration::from_millis(200));

    let capture_result = (|| {
        let display =
            Display::primary().map_err(|e| format!("Failed to get primary display: {}", e))?;
        let mut capturer =
            Capturer::new(display).map_err(|e| format!("Failed to create capturer: {}", e))?;

        let (w, h) = (capturer.width(), capturer.height());

        // Try to capture a frame (may need a few attempts)
        let mut attempts = 0;
        let frame = loop {
            match capturer.frame() {
                Ok(frame) => break frame,
                Err(error) => {
                    if attempts > 10 {
                        return Err(format!(
                            "Failed to capture screen after 10 attempts: {}",
                            error
                        ));
                    }
                    attempts += 1;
                    thread::sleep(Duration::from_millis(100));
                }
            }
        };

        // Convert BGRA to RGBA
        let mut rgba_data = Vec::with_capacity(frame.len());
        for bgra in frame.chunks_exact(4) {
            rgba_data.push(bgra[2]); // R
            rgba_data.push(bgra[1]); // G
            rgba_data.push(bgra[0]); // B
            rgba_data.push(bgra[3]); // A
        }

        // Create image
        let mut img = RgbaImage::from_raw(w as u32, h as u32, rgba_data)
            .ok_or("Failed to create image from raw data")?;

        // Add grid overlay
        add_grid_overlay(&mut img)?;

        Ok(img) // Return the RgbaImage
    })();

    // IMPORTANT: Ensure the window is shown again, regardless of capture outcome.
    window
        .show()
        .map_err(|e| format!("Failed to show window: {}", e))?;

    capture_result
}

#[tauri::command]
async fn chat_with_gpt(message: String) -> Result<String, String> {
    // Load environment variables
    if let Err(e) = load_env() {
        return Err(format!("Environment setup failed: {}", e));
    }

    let api_key = env::var("OPENAI_API_KEY")
        .map_err(|_| {
            "OPENAI_API_KEY not found. Please:\n1. Create a .env file in src-tauri/ directory\n2. Add: OPENAI_API_KEY=your-actual-api-key\n3. Get your API key from: https://platform.openai.com/api-keys".to_string()
        })?;

    if api_key == "your-openai-api-key-here" || api_key.is_empty() {
        return Err("Please replace 'your-openai-api-key-here' with your actual OpenAI API key in the .env file".to_string());
    }

    let client = Client::new();

    let request_body = ChatRequest {
        model: "gpt-4.1-nano-2025-04-14",
        messages: vec![ChatMessage {
            role: "user".to_string(),
            content: message.clone(),
        }],
    };

    // Debug log: record the prompt being sent to the model
    if let Ok(json_prompt) = serde_json::to_string(&request_body) {
        add_log(
            "PROMPT",
            "chat_with_gpt",
            None,
            Some(json_prompt),
            true,
            None,
        );
    }

    println!("Sending request to OpenAI API...");

    let response = client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&request_body)
        .send()
        .await
        .map_err(|e| format!("Network error: {}", e))?;

    if response.status().is_success() {
        let chat_response = response
            .json::<ChatResponse>()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;
        if let Some(choice) = chat_response.choices.get(0) {
            Ok(choice.message.content.clone())
        } else {
            Err("No response from API".to_string())
        }
    } else {
        let status = response.status();
        let error_body = response.text().await.map_err(|e| e.to_string())?;
        Err(format!(
            "API request failed with status {}: {}",
            status, error_body
        ))
    }
}

#[tauri::command]
async fn chat_with_vision(message: String, image_data: String) -> Result<String, String> {
    // Load environment variables
    if let Err(e) = load_env() {
        return Err(format!("Environment setup failed: {}", e));
    }

    let api_key = env::var("OPENAI_API_KEY")
        .map_err(|_| {
            "OPENAI_API_KEY not found. Please:\n1. Create a .env file in src-tauri/ directory\n2. Add: OPENAI_API_KEY=your-actual-api-key\n3. Get your API key from: https://platform.openai.com/api-keys".to_string()
        })?;

    if api_key == "your-openai-api-key-here" || api_key.is_empty() {
        return Err("Please replace 'your-openai-api-key-here' with your actual OpenAI API key in the .env file".to_string());
    }

    let client = Client::new();

    let vision_message = VisionMessage {
        role: "user".to_string(),
        content: vec![
            ContentPart {
                content_type: "text".to_string(),
                text: Some(message),
                image_url: None,
            },
            ContentPart {
                content_type: "image_url".to_string(),
                text: None,
                image_url: Some(ImageUrl {
                    url: format!("data:image/png;base64,{}", image_data),
                    detail: "high".to_string(),
                }),
            },
        ],
    };

    let request_body = VisionRequest {
        model: "gpt-4.1-nano-2025-04-14",
        messages: vec![vision_message],
        max_tokens: 1000,
    };

    // Debug log: record the prompt being sent to the vision model
    if let Ok(json_prompt) = serde_json::to_string(&request_body) {
        add_log(
            "PROMPT",
            "chat_with_vision",
            None,
            Some(json_prompt),
            true,
            None,
        );
    }

    println!("Sending vision request to OpenAI API...");

    let response = client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&request_body)
        .send()
        .await
        .map_err(|e| format!("Network error: {}", e))?;

    if response.status().is_success() {
        let vision_response = response
            .json::<VisionResponse>()
            .await
            .map_err(|e| format!("Failed to parse response: {}", e))?;
        if let Some(choice) = vision_response.choices.get(0) {
            Ok(choice.message.content.clone())
        } else {
            Err("No response from API".to_string())
        }
    } else {
        let status = response.status();
        let error_body = response.text().await.map_err(|e| e.to_string())?;
        Err(format!(
            "API request failed with status {}: {}",
            status, error_body
        ))
    }
}

#[tauri::command]
async fn test_env() -> Result<String, String> {
    let mut debug_info = String::new();

    // Show current working directory
    match std::env::current_dir() {
        Ok(dir) => debug_info.push_str(&format!("📁 Current directory: {}\n", dir.display())),
        Err(e) => debug_info.push_str(&format!("❌ Could not get current directory: {}\n", e)),
    }

    // Test environment loading
    match load_env() {
        Ok(_) => debug_info.push_str("✅ Environment loading succeeded\n"),
        Err(e) => {
            debug_info.push_str(&format!("❌ Environment loading failed: {}\n", e));
            return Ok(debug_info);
        }
    }

    // Check API key
    match env::var("OPENAI_API_KEY") {
        Ok(key) => {
            if key.is_empty() {
                debug_info.push_str("❌ OPENAI_API_KEY is empty\n");
            } else if key == "your-openai-api-key-here" {
                debug_info.push_str("❌ OPENAI_API_KEY is still the placeholder value\n");
            } else if key.starts_with("sk-") {
                debug_info.push_str(&format!(
                    "✅ OPENAI_API_KEY found (length: {} chars, starts with 'sk-')\n",
                    key.len()
                ));
            } else {
                debug_info.push_str(&format!(
                    "⚠️ OPENAI_API_KEY found but doesn't start with 'sk-' (length: {} chars)\n",
                    key.len()
                ));
            }
        }
        Err(_) => debug_info.push_str("❌ OPENAI_API_KEY not found in environment\n"),
    }

    Ok(debug_info)
}

#[tauri::command]
async fn start_automation(window: tauri::Window, goal: String) -> Result<String, String> {
    run_full_automation(window, goal).await
}

#[tauri::command]
async fn run_full_automation(window: tauri::Window, goal: String) -> Result<String, String> {
    // Log automation start
    add_log(
        "AUTOMATION",
        &format!("Started full automation with goal: {}", goal),
        None,
        Some(goal.clone()),
        true,
        None,
    );

    let max_steps = 20; // Safety limit to prevent infinite loops
    let mut step_count = 0;
    let mut previous_instruction: Option<String> = None;
    let mut all_steps = Vec::new();

    while step_count < max_steps {
        step_count += 1;

        // Log current step
        add_log(
            "AUTOMATION",
            &format!("Executing step {}/{}", step_count, max_steps),
            None,
            Some(format!("Goal: {}", goal)),
            true,
            None,
        );

        // Capture screen
        let screen_image = capture_screen(window.clone()).await?;
        let (width, height) = screen_image.dimensions();

        // Encode the full image for the vision model
        let screenshot_b64 = {
            let mut png_bytes = Vec::new();
            let mut cursor = Cursor::new(&mut png_bytes);
            screen_image
                .write_to(&mut cursor, ImageFormat::Png)
                .map_err(|e| format!("Failed to encode full PNG: {}", e))?;
            BASE64.encode(&png_bytes)
        };

        // Create automation prompt
        let automation_prompt = create_enhanced_automation_prompt(
            &goal,
            previous_instruction.as_deref(),
            Some(step_count - 1),
            width,
            height,
        );

        // Debug log: record automation prompt sent to model
        add_log(
            "PROMPT",
            &format!("run_full_automation_step_{}", step_count),
            None,
            Some(automation_prompt.clone()),
            true,
            None,
        );

        println!(
            "\n\n--- STEP {} PROMPT SENT TO MODEL ---\n{}\n--- END OF PROMPT ---\n",
            step_count, automation_prompt
        );

        // Get instruction from the model
        let response = match chat_with_vision(automation_prompt, screenshot_b64.clone()).await {
            Ok(response) => response,
            Err(error) => {
                add_log(
                    "AUTOMATION",
                    &format!(
                        "Failed to get automation instruction for step {}",
                        step_count
                    ),
                    None,
                    None,
                    false,
                    Some(error.clone()),
                );
                return Err(format!("Step {}: {}", step_count, error));
            }
        };

        // Log AI instruction
        add_log(
            "AI_INSTRUCTION",
            &format!("Step {}: {}", step_count, response),
            None,
            Some(response.clone()),
            true,
            None,
        );

        // Check if task is completed
        if response.contains("TASK COMPLETED") {
            all_steps.push(format!("Step {}: {}", step_count, response));
            add_log(
                "AUTOMATION",
                "Task completed successfully",
                None,
                Some(format!("Completed in {} steps", step_count)),
                true,
                None,
            );

            let final_response = AutomationResponse {
                instruction: format!(
                    "✅ Task completed in {} steps!\n\nSteps taken:\n{}",
                    step_count,
                    all_steps.join("\n")
                ),
                completed: true,
                next_action: "done".to_string(),
                coordinates: None,
                text_to_type: None,
                screenshot: Some(screenshot_b64),
            };

            return Ok(serde_json::to_string(&final_response).unwrap());
        }

        // Execute the action
        match execute_enhanced_automation_action(&response) {
            Ok(execution_result) => {
                add_log(
                    "EXECUTION_SUCCESS",
                    &format!(
                        "Step {} executed successfully: {}",
                        step_count, execution_result
                    ),
                    None,
                    Some(response.clone()),
                    true,
                    None,
                );
                all_steps.push(format!(
                    "Step {}: {} → {}",
                    step_count, response, execution_result
                ));
            }
            Err(execution_error) => {
                add_log(
                    "EXECUTION_ERROR",
                    &format!("Step {} failed: {}", step_count, execution_error),
                    None,
                    Some(response.clone()),
                    false,
                    Some(execution_error.clone()),
                );
                all_steps.push(format!(
                    "Step {}: {} → ERROR: {}",
                    step_count, response, execution_error
                ));
            }
        }

        // Store current instruction for next iteration
        previous_instruction = Some(response);

        // Small delay between steps to allow UI to update
        tokio::time::sleep(tokio::time::Duration::from_millis(1000)).await;
    }

    // If we reach here, we've hit the max steps limit
    add_log(
        "AUTOMATION",
        "Maximum steps reached without completion",
        None,
        Some(format!("Reached max steps: {}", max_steps)),
        false,
        None,
    );

    let final_response = AutomationResponse {
        instruction: format!(
            "⚠️ Automation stopped after {} steps (maximum limit reached).\n\nSteps taken:\n{}",
            max_steps,
            all_steps.join("\n")
        ),
        completed: false,
        next_action: "timeout".to_string(),
        coordinates: None,
        text_to_type: None,
        screenshot: None,
    };

    Ok(serde_json::to_string(&final_response).unwrap())
}

#[tauri::command]
async fn continue_automation(
    window: tauri::Window,
    goal: String,
    previous_instruction: String,
    step_count: u32,
) -> Result<String, String> {
    // For backwards compatibility, redirect to the new full automation system
    // This will restart the automation process rather than continuing from a specific step
    run_full_automation(window, goal).await
}

#[tauri::command]
async fn get_automation_screenshot(window: tauri::Window) -> Result<String, String> {
    // Get the raw image
    let img = capture_screen(window).await?;

    // Encode it to PNG
    let mut png_bytes = Vec::new();
    let mut cursor = Cursor::new(&mut png_bytes);
    img.write_to(&mut cursor, ImageFormat::Png)
        .map_err(|e| format!("Failed to encode PNG: {}", e))?;

    // Encode to base64
    let base64_image = BASE64.encode(&png_bytes);
    Ok(base64_image)
}

#[tauri::command]
async fn get_action_logs() -> Result<Vec<ActionLog>, String> {
    let logs = ACTION_LOGS.get().ok_or("Action logs not initialized")?;
    let logs_guard = logs.lock().unwrap();
    Ok(logs_guard.clone())
}

#[tauri::command]
async fn clear_action_logs() -> Result<String, String> {
    let logs = ACTION_LOGS.get().ok_or("Action logs not initialized")?;
    let mut logs_guard = logs.lock().unwrap();
    logs_guard.clear();

    // Reset counter
    let counter = LOG_ID_COUNTER
        .get()
        .ok_or("Log ID counter not initialized")?;
    let mut counter_guard = counter.lock().unwrap();
    *counter_guard = 0;

    Ok("Action logs cleared successfully".to_string())
}

#[tauri::command]
async fn log_manual_action(
    action_type: String,
    description: String,
    coordinates: Option<(u32, u32)>,
    text_content: Option<String>,
) -> Result<String, String> {
    add_log(
        &action_type,
        &description,
        coordinates,
        text_content,
        true,
        None,
    );
    Ok("Action logged successfully".to_string())
}

#[tauri::command]
async fn discover_ui_elements_command() -> Result<Vec<UIElement>, String> {
    discover_ui_elements()
}

#[tauri::command]
async fn get_ui_summary_command() -> Result<UIElementSummary, String> {
    get_ui_elements_summary()
}

#[tauri::command]
async fn find_ui_element_command(description: String) -> Result<Option<UIElement>, String> {
    find_ui_element_by_description(&description)
}

#[tauri::command]
async fn execute_ui_action_command(instruction: String) -> Result<String, String> {
    execute_enhanced_automation_action(&instruction)
}

// Browser Automation Commands
#[tauri::command]
async fn discover_browser_elements_command(
    target_browser: Option<String>,
) -> Result<serde_json::Value, String> {
    discover_browser_elements_rust(target_browser.as_deref())
}

#[tauri::command]
async fn get_browser_summary_command(
    target_browser: Option<String>,
) -> Result<serde_json::Value, String> {
    get_browser_elements_summary_rust(target_browser.as_deref())
}

#[tauri::command]
async fn find_browser_element_command(
    description: String,
    target_browser: Option<String>,
) -> Result<Option<serde_json::Value>, String> {
    find_browser_element_by_description_rust(&description, target_browser.as_deref())
}

#[tauri::command]
async fn execute_browser_action_command(instruction: String) -> Result<String, String> {
    // For now, use the enhanced automation action which includes UI automation
    // In the future, we could add browser-specific automation here
    execute_enhanced_automation_action(&instruction)
}

#[tauri::command]
async fn get_chrome_elements_command() -> Result<serde_json::Value, String> {
    discover_browser_elements_rust(Some("chrome"))
}

// Host Screen Detection Commands
#[tauri::command]
async fn discover_host_screen_elements_command() -> Result<serde_json::Value, String> {
    discover_host_screen_elements()
}

#[tauri::command]
async fn get_host_screen_summary_command() -> Result<serde_json::Value, String> {
    get_host_screen_elements_summary()
}

fn main() {
    // Initialize logging system
    init_logging();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            chat_with_gpt,
            chat_with_vision,
            test_env,
            start_automation,
            run_full_automation,
            continue_automation,
            get_automation_screenshot,
            get_action_logs,
            clear_action_logs,
            log_manual_action,
            discover_ui_elements_command,
            get_ui_summary_command,
            find_ui_element_command,
            execute_ui_action_command,
            discover_browser_elements_command,
            get_browser_summary_command,
            find_browser_element_command,
            execute_browser_action_command,
            get_chrome_elements_command,
            discover_host_screen_elements_command,
            get_host_screen_summary_command,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
