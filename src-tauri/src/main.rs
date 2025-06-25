// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use chrono::{DateTime, Utc};
use dotenvy::dotenv;
use enigo::{Button, Direction, Enigo, Key, Keyboard, Mouse, Settings};
use image::{ImageFormat, Rgba, RgbaImage};
use reqwest::Client;
use scrap::{Capturer, Display};
use serde::{Deserialize, Serialize};
use std::env;
use std::io::Cursor;
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::Duration;

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

            return Ok(format!("✓ Clicked at coordinates ({}, {})", x, y));
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

            return Ok(format!("✓ Typed: {}", text));
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

            return Ok(format!("✓ Pressed {}", key_name));
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
            "✓ Scrolled {}",
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

#[tauri::command]
async fn capture_screen() -> Result<String, String> {
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
        };
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

    // Convert to PNG bytes
    let mut png_bytes = Vec::new();
    let mut cursor = Cursor::new(&mut png_bytes);
    img.write_to(&mut cursor, ImageFormat::Png)
        .map_err(|e| format!("Failed to encode PNG: {}", e))?;

    // Encode to base64
    let base64_image = BASE64.encode(&png_bytes);
    Ok(base64_image)
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
        model: "gpt-4o-mini",
        messages: vec![ChatMessage {
            role: "user".to_string(),
            content: message,
        }],
    };

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
                }),
            },
        ],
    };

    let request_body = VisionRequest {
        model: "gpt-4o-mini",
        messages: vec![vision_message],
        max_tokens: 1000,
    };

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
async fn start_automation(goal: String) -> Result<String, String> {
    // Log automation start
    add_log(
        "AUTOMATION",
        &format!("Started automation with goal: {}", goal),
        None,
        Some(goal.clone()),
        true,
        None,
    );

    // Capture screen first
    let screenshot = capture_screen().await?;

    // Get first instruction from the model
    let automation_prompt = format!(
        "AUTOMATION TASK: {}

You are an automation assistant that controls computer actions. I will provide screenshots with a grid overlay for precise positioning.

🎯 GRID SYSTEM:
- Grid squares are 75x75 pixels each
- Coordinates are labeled at intersections like (75,75), (150,150), (225,225), etc.
- Red grid lines help you identify precise locations
- Use coordinates from the grid labels for maximum accuracy

⚡ AVAILABLE ACTIONS:

1. CLICK ACTIONS:
   - Format: 'Click [description] at coordinates (x, y)'
   - Examples: 
     • 'Click the search button at coordinates (400, 150)'
     • 'Click the menu icon at coordinates (50, 100)'
     • 'Click coordinates (700, 300)' (if no clear element description)

2. TYPING ACTIONS:
   - Format: 'Type \"[exact text]\" [optional location description]'
   - Examples:
     • 'Type \"Hello World\" in the text field'
     • 'Type \"john@example.com\"'
     • 'Type \"password123\"'

3. KEYBOARD SHORTCUTS & KEYS:
   - Format: 'Press [key name]'
   - Supported keys: Enter, Return, Tab, Escape, Space
   - Examples:
     • 'Press Enter' (submit forms, confirm)
     • 'Press Tab' (navigate fields)
     • 'Press Escape' (close dialogs)

4. SCROLL ACTIONS:
   - Format: 'Scroll [direction]'
   - Examples:
     • 'Scroll down' (scroll down the page)
     • 'Scroll up' (scroll up the page)

📋 RESPONSE RULES:
1. Give ONE specific action at a time
2. Always use exact grid coordinates when clicking
3. Be precise about what you're clicking (button, link, field, etc.)
4. For typing, use exact quotes around the text
5. If goal is completed, say 'TASK COMPLETED - [brief description]'

✅ GOOD EXAMPLES:
- 'Click the login button at coordinates (350, 450)'
- 'Type \"admin\" in the username field'
- 'Press Enter to submit the form'
- 'Scroll down to see more options'
- 'TASK COMPLETED - Successfully logged into the system'

❌ AVOID:
- Vague coordinates like 'near the top' or 'bottom right'
- Missing quotes around text to type
- Multiple actions in one instruction
- Unclear element descriptions

What is the first action I should take to accomplish this goal?", 
        goal
    );

    match chat_with_vision(automation_prompt, screenshot.clone()).await {
        Ok(response) => {
            // Log automation step
            add_log(
                "AI_INSTRUCTION",
                &format!("Step 1: {}", response),
                None,
                Some(response.clone()),
                true,
                None,
            );

            // Execute the automation action
            let final_response = match execute_automation_action(&response) {
                Ok(execution_result) => {
                    // Return both the instruction and execution result
                    format!("{}\n{}", response, execution_result)
                }
                Err(execution_error) => {
                    // Log execution error but still return the instruction
                    add_log(
                        "EXECUTION_ERROR",
                        &format!("Failed to execute: {}", execution_error),
                        None,
                        Some(response.clone()),
                        false,
                        Some(execution_error.clone()),
                    );
                    format!("{}\n❌ Execution failed: {}", response, execution_error)
                }
            };

            // Return response with screenshot
            let automation_response = AutomationResponse {
                instruction: final_response,
                completed: response.contains("TASK COMPLETED"),
                next_action: "click".to_string(), // Default action type
                coordinates: extract_coordinates(&response),
                text_to_type: extract_text_to_type(&response),
                screenshot: Some(screenshot),
            };

            Ok(serde_json::to_string(&automation_response).unwrap())
        }
        Err(error) => {
            // Log automation error
            add_log(
                "AUTOMATION",
                "Failed to get automation instruction",
                None,
                None,
                false,
                Some(error.clone()),
            );
            Err(error)
        }
    }
}

#[tauri::command]
async fn continue_automation(
    goal: String,
    previous_instruction: String,
    step_count: u32,
) -> Result<String, String> {
    // Log automation continuation
    add_log(
        "AUTOMATION",
        &format!("Continuing automation - Step {}", step_count + 1),
        None,
        Some(format!(
            "Goal: {} | Previous: {}",
            goal, previous_instruction
        )),
        true,
        None,
    );

    // Capture current screen state
    let screenshot = capture_screen().await?;

    // Create context-aware prompt
    let automation_prompt = format!(
        "AUTOMATION TASK CONTINUATION: {}

Previous step #{}: {}

I've taken the previous action. Here's the current screenshot with grid overlay.

🎯 GRID SYSTEM:
- Grid squares are 50x50 pixels each
- Coordinates are labeled at intersections like (50,50), (100,100), (150,150), etc.
- Red grid lines help you identify precise locations
- Use coordinates from the grid labels for maximum accuracy

⚡ AVAILABLE ACTIONS:

1. CLICK ACTIONS:
   - Format: 'Click [description] at coordinates (x, y)'
   - Examples: 
     • 'Click the search button at coordinates (400, 150)'
     • 'Click the menu icon at coordinates (50, 100)'
     • 'Click coordinates (700, 300)' (if no clear element description)

2. TYPING ACTIONS:
   - Format: 'Type \"[exact text]\" [optional location description]'
   - Examples:
     • 'Type \"Hello World\" in the text field'
     • 'Type \"john@example.com\"'
     • 'Type \"password123\"'

3. KEYBOARD SHORTCUTS & KEYS:
   - Format: 'Press [key name]'
   - Supported keys: Enter, Return, Tab, Escape, Space
   - Examples:
     • 'Press Enter' (submit forms, confirm)
     • 'Press Tab' (navigate fields)
     • 'Press Escape' (close dialogs)

4. SCROLL ACTIONS:
   - Format: 'Scroll [direction]'
   - Examples:
     • 'Scroll down' (scroll down the page)
     • 'Scroll up' (scroll up the page)

📋 RESPONSE RULES:
1. Give ONE specific action at a time
2. Always use exact grid coordinates when clicking
3. Be precise about what you're clicking (button, link, field, etc.)
4. For typing, use exact quotes around the text
5. Consider what changed from the previous action
6. If goal is completed, say 'TASK COMPLETED - [brief description]'

✅ GOOD EXAMPLES:
- 'Click the login button at coordinates (350, 450)'
- 'Type \"admin\" in the username field'
- 'Press Enter to submit the form'
- 'Scroll down to see more options'
- 'TASK COMPLETED - Successfully logged into the system'

❌ AVOID:
- Vague coordinates like 'near the top' or 'bottom right'
- Missing quotes around text to type
- Multiple actions in one instruction
- Unclear element descriptions

Analyze the current state and provide the NEXT SINGLE ACTION to continue toward the goal. What should I do next?", 
        goal, step_count, previous_instruction
    );

    match chat_with_vision(automation_prompt, screenshot.clone()).await {
        Ok(response) => {
            // Log automation step
            add_log(
                "AI_INSTRUCTION",
                &format!("Step {}: {}", step_count + 1, response),
                None,
                Some(response.clone()),
                true,
                None,
            );

            // Execute the automation action
            let final_response = match execute_automation_action(&response) {
                Ok(execution_result) => {
                    // Return both the instruction and execution result
                    format!("{}\n{}", response, execution_result)
                }
                Err(execution_error) => {
                    // Log execution error but still return the instruction
                    add_log(
                        "EXECUTION_ERROR",
                        &format!("Failed to execute: {}", execution_error),
                        None,
                        Some(response.clone()),
                        false,
                        Some(execution_error.clone()),
                    );
                    format!("{}\n❌ Execution failed: {}", response, execution_error)
                }
            };

            // Return response with screenshot
            let automation_response = AutomationResponse {
                instruction: final_response,
                completed: response.contains("TASK COMPLETED"),
                next_action: "click".to_string(), // Default action type
                coordinates: extract_coordinates(&response),
                text_to_type: extract_text_to_type(&response),
                screenshot: Some(screenshot),
            };

            Ok(serde_json::to_string(&automation_response).unwrap())
        }
        Err(error) => {
            // Log automation error
            add_log(
                "AUTOMATION",
                &format!(
                    "Failed to get automation instruction for step {}",
                    step_count + 1
                ),
                None,
                None,
                false,
                Some(error.clone()),
            );
            Err(error)
        }
    }
}

#[tauri::command]
async fn get_automation_screenshot() -> Result<String, String> {
    // Simply capture and return screenshot with grid
    capture_screen().await
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

fn main() {
    // Initialize logging system
    init_logging();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            chat_with_gpt,
            capture_screen,
            chat_with_vision,
            test_env,
            start_automation,
            continue_automation,
            get_automation_screenshot,
            get_action_logs,
            clear_action_logs,
            log_manual_action
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
