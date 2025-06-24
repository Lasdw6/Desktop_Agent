// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use dotenvy::dotenv;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::env;
use scrap::{Capturer, Display};
use image::{ImageFormat, RgbaImage};
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use std::io::Cursor;
use std::thread;
use std::time::Duration;

// Load environment variables from .env file
fn load_env() -> Result<(), String> {
    // Try multiple locations for .env file
    let env_paths = vec![
        ".env",                    // Current directory (src-tauri/.env when running from src-tauri)
        "src-tauri/.env",         // From project root
        "../.env",                // Parent directory
        "./.env",                 // Explicit current directory
    ];
    
    let mut last_error = String::new();
    
    for path in env_paths {
        match dotenvy::from_path(path) {
            Ok(_) => {
                println!("Successfully loaded .env from: {}", path);
                return Ok(());
            },
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
    
    Err(format!("Could not find .env file in any location. Last error: {}", last_error))
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

#[tauri::command]
async fn capture_screen() -> Result<String, String> {
    let display = Display::primary().map_err(|e| format!("Failed to get primary display: {}", e))?;
    let mut capturer = Capturer::new(display).map_err(|e| format!("Failed to create capturer: {}", e))?;
    
    let (w, h) = (capturer.width(), capturer.height());
    
    // Try to capture a frame (may need a few attempts)
    let mut attempts = 0;
    let frame = loop {
        match capturer.frame() {
            Ok(frame) => break frame,
            Err(error) => {
                if attempts > 10 {
                    return Err(format!("Failed to capture screen after 10 attempts: {}", error));
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
    let img = RgbaImage::from_raw(w as u32, h as u32, rgba_data)
        .ok_or("Failed to create image from raw data")?;
    
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
        Err(format!("API request failed with status {}: {}", status, error_body))
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
        model: "gpt-4o",
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
        Err(format!("API request failed with status {}: {}", status, error_body))
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
                debug_info.push_str(&format!("✅ OPENAI_API_KEY found (length: {} chars, starts with 'sk-')\n", key.len()));
            } else {
                debug_info.push_str(&format!("⚠️ OPENAI_API_KEY found but doesn't start with 'sk-' (length: {} chars)\n", key.len()));
            }
        },
        Err(_) => debug_info.push_str("❌ OPENAI_API_KEY not found in environment\n")
    }
    
    Ok(debug_info)
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![chat_with_gpt, capture_screen, chat_with_vision, test_env])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
