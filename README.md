# Desktop Assistant

A desktop AI assistant built with Tauri, React, and TypeScript that provides ChatGPT integration with screen capture capabilities.

## Features

- 🤖 **ChatGPT Integration**: Chat with GPT-4o-mini for text conversations
- 📷 **Screen Capture**: Capture and analyze screenshots with GPT-4o-mini Vision
- 🪟 **Minimized Bar Interface**: Always-on-top minimized bar that expands when needed
- 🎨 **Modern UI**: Glass morphism design with translucent backgrounds
- ⚡ **Fast**: Built with Rust backend and React frontend

## Setup Instructions

### Prerequisites

- [Node.js](https://nodejs.org/) (v16 or higher)
- [Rust](https://rustup.rs/) (latest stable)
- [OpenAI API Key](https://platform.openai.com/api-keys)

### Installation

1. **Clone the repository**

   ```bash
   git clone <your-repo-url>
   cd Desktop_Agent
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Set up your OpenAI API Key**

   - Create a `.env` file in the `src-tauri/` directory
   - Add your OpenAI API key:
     ```
     OPENAI_API_KEY=your-actual-api-key-here
     ```
   - Get your API key from: https://platform.openai.com/api-keys

4. **Run the application**
   ```bash
   npm run tauri dev
   ```

## Usage

### Minimized Mode

- The app starts as a minimized bar at the bottom of your screen
- Click the input field or buttons to expand the chat interface

### Chat Features

- **Text Chat**: Type messages to chat with GPT-4o-mini
- **Screen Capture**: Click the 📷 button to capture your screen and analyze it with GPT-4o-mini Vision
- **Auto-Resize**: The window automatically resizes based on content

### Keyboard Shortcuts

- `Enter`: Send message
- `Shift + Enter`: New line in message input

## Development

### Project Structure

```
Desktop_Agent/
├── src/                    # React frontend
│   ├── App.tsx            # Main application component
│   ├── App.css            # Styling
│   └── ...
├── src-tauri/             # Rust backend
│   ├── src/
│   │   ├── main.rs        # Main Rust application
│   │   └── lib.rs
│   ├── .env               # Environment variables (not in git)
│   └── ...
└── README.md
```

### Available Commands

- `npm run tauri dev` - Start development server
- `npm run tauri build` - Build for production
- `npm run dev` - Start Vite dev server only
- `npm run build` - Build frontend only

### API Commands

The Rust backend exposes these Tauri commands:

- `capture_screen()` - Captures the primary display
- `chat_with_gpt(message)` - Sends text to GPT-4o-mini
- `chat_with_vision(message, image_data)` - Sends text + image to GPT-4o-mini Vision
- `test_env()` - Tests environment variable loading (debug)

## Configuration

### Environment Variables

Create `src-tauri/.env` with:

```
OPENAI_API_KEY=your-openai-api-key-here
```

### Window Settings

The app is configured for:

- Always on top
- No window decorations
- Transparent background support
- Auto-positioning at screen bottom

## Troubleshooting

### API Key Issues

- Ensure `.env` file is in `src-tauri/` directory
- Check that there are no trailing spaces in your API key
- Use the 🔑 test button to verify API key loading

### Screen Capture Issues

- Make sure you have proper permissions for screen capture
- The app may need to be granted accessibility permissions on macOS

### Build Issues

- Ensure Rust and Node.js are properly installed
- Try `cargo clean` in the `src-tauri/` directory if Rust build fails

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)

## License

This project is open source. Feel free to use and modify as needed.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request
