# -*- coding: utf-8 -*-
"""Modern Design System for VGC MCP UI.

Provides CSS variables, animations, and utility functions for creating
beautiful, interactive UI components with glassmorphism effects.
"""

from typing import Optional

# =============================================================================
# CSS DESIGN TOKENS
# =============================================================================

DESIGN_TOKENS = """
:root {
    /* ===== COLORS ===== */
    /* Base backgrounds */
    --bg-primary: #0a0a1a;
    --bg-secondary: #12122a;
    --bg-card: #1a1a3a;
    --bg-elevated: #222250;

    /* Glassmorphism */
    --glass-bg: rgba(255, 255, 255, 0.03);
    --glass-bg-hover: rgba(255, 255, 255, 0.06);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-border-hover: rgba(255, 255, 255, 0.15);
    --glass-blur: 20px;
    --glass-shine: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%, transparent 100%);

    /* Text colors */
    --text-primary: #ffffff;
    --text-secondary: rgba(255, 255, 255, 0.7);
    --text-muted: rgba(255, 255, 255, 0.5);
    --text-accent: #8b5cf6;

    /* Accent colors */
    --accent-primary: #6366f1;
    --accent-secondary: #8b5cf6;
    --accent-success: #22c55e;
    --accent-warning: #f59e0b;
    --accent-danger: #ef4444;
    --accent-info: #06b6d4;

    /* Gradients */
    --gradient-primary: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    --gradient-success: linear-gradient(135deg, #22c55e 0%, #4ade80 100%);
    --gradient-danger: linear-gradient(135deg, #ef4444 0%, #f87171 100%);
    --gradient-warning: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
    --gradient-info: linear-gradient(135deg, #06b6d4 0%, #22d3ee 100%);
    --gradient-rainbow: linear-gradient(135deg, #6366f1, #8b5cf6, #d946ef, #f43f5e);

    /* Glow effects */
    --glow-primary: 0 0 30px rgba(99, 102, 241, 0.4);
    --glow-success: 0 0 30px rgba(34, 197, 94, 0.4);
    --glow-danger: 0 0 30px rgba(239, 68, 68, 0.4);
    --glow-warning: 0 0 30px rgba(245, 158, 11, 0.4);

    /* ===== SPACING ===== */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    --space-2xl: 48px;

    /* ===== TYPOGRAPHY ===== */
    --font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    --font-size-xs: 11px;
    --font-size-sm: 13px;
    --font-size-md: 15px;
    --font-size-lg: 18px;
    --font-size-xl: 24px;
    --font-size-2xl: 32px;
    --font-weight-normal: 400;
    --font-weight-medium: 500;
    --font-weight-bold: 700;

    /* ===== BORDERS ===== */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 24px;
    --radius-full: 9999px;

    /* ===== SHADOWS ===== */
    --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.2);
    --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.3);
    --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.4);
    --shadow-xl: 0 16px 48px rgba(0, 0, 0, 0.5);
    --shadow-inset: inset 0 1px 0 rgba(255, 255, 255, 0.03);

    /* ===== ANIMATION ===== */
    --ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
    --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
    --ease-elastic: cubic-bezier(0.68, -0.6, 0.32, 1.6);
    --duration-fast: 150ms;
    --duration-normal: 300ms;
    --duration-slow: 500ms;
}
"""

# =============================================================================
# CSS ANIMATIONS
# =============================================================================

ANIMATIONS = """
/* ===== ENTRANCE ANIMATIONS ===== */
@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes fadeSlideInLeft {
    from { opacity: 0; transform: translateX(-20px); }
    to { opacity: 1; transform: translateX(0); }
}

@keyframes fadeSlideInRight {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
}

@keyframes scaleIn {
    from { opacity: 0; transform: scale(0.9); }
    to { opacity: 1; transform: scale(1); }
}

@keyframes popIn {
    0% { opacity: 0; transform: scale(0.5); }
    70% { transform: scale(1.1); }
    100% { opacity: 1; transform: scale(1); }
}

/* ===== CONTINUOUS ANIMATIONS ===== */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

@keyframes pulseGlow {
    0%, 100% { box-shadow: var(--glow-primary); }
    50% { box-shadow: 0 0 50px rgba(99, 102, 241, 0.6); }
}

@keyframes pulseGlowDanger {
    0%, 100% { box-shadow: var(--glow-danger); }
    50% { box-shadow: 0 0 50px rgba(239, 68, 68, 0.7); }
}

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-6px); }
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

/* ===== SPRITE ANIMATIONS ===== */
@keyframes spriteBounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

@keyframes spriteEntrance {
    0% { opacity: 0; transform: scale(0.7) translateY(30px); }
    60% { transform: scale(1.05) translateY(-5px); }
    100% { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes spriteHover {
    0%, 100% { transform: translateY(0) rotate(0deg); }
    25% { transform: translateY(-3px) rotate(-2deg); }
    75% { transform: translateY(-3px) rotate(2deg); }
}

/* ===== DAMAGE/STATS ANIMATIONS ===== */
@keyframes damageFill {
    from { width: 0%; }
    to { width: var(--damage-percent, 100%); }
}

@keyframes numberPop {
    0% { opacity: 0; transform: scale(0.5) translateY(10px); }
    60% { transform: scale(1.2) translateY(-5px); }
    100% { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes statBarFill {
    from { transform: scaleX(0); }
    to { transform: scaleX(1); }
}

@keyframes countUp {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* ===== INTERACTION ANIMATIONS ===== */
@keyframes buttonPress {
    0% { transform: scale(1); }
    50% { transform: scale(0.95); }
    100% { transform: scale(1); }
}

@keyframes ripple {
    0% { transform: scale(0); opacity: 0.5; }
    100% { transform: scale(4); opacity: 0; }
}

@keyframes shake {
    0%, 100% { transform: translateX(0); }
    20%, 60% { transform: translateX(-5px); }
    40%, 80% { transform: translateX(5px); }
}

/* ===== LOADING ANIMATIONS ===== */
@keyframes skeletonPulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.7; }
}

@keyframes loadingDots {
    0%, 20% { content: '.'; }
    40% { content: '..'; }
    60%, 100% { content: '...'; }
}

/* ===== CARD ANIMATIONS ===== */
@keyframes cardShine {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes cardLift {
    from { transform: translateY(0); box-shadow: var(--shadow-md); }
    to { transform: translateY(-8px); box-shadow: var(--shadow-xl); }
}
"""

# =============================================================================
# POKEMON TYPE COLORS (Official)
# =============================================================================

TYPE_COLORS = {
    "normal": {"bg": "#A8A878", "text": "#000"},
    "fire": {"bg": "#F08030", "text": "#fff"},
    "water": {"bg": "#6890F0", "text": "#fff"},
    "electric": {"bg": "#F8D030", "text": "#000"},
    "grass": {"bg": "#78C850", "text": "#000"},
    "ice": {"bg": "#98D8D8", "text": "#000"},
    "fighting": {"bg": "#C03028", "text": "#fff"},
    "poison": {"bg": "#A040A0", "text": "#fff"},
    "ground": {"bg": "#E0C068", "text": "#000"},
    "flying": {"bg": "#A890F0", "text": "#000"},
    "psychic": {"bg": "#F85888", "text": "#fff"},
    "bug": {"bg": "#A8B820", "text": "#000"},
    "rock": {"bg": "#B8A038", "text": "#000"},
    "ghost": {"bg": "#705898", "text": "#fff"},
    "dragon": {"bg": "#7038F8", "text": "#fff"},
    "dark": {"bg": "#705848", "text": "#fff"},
    "steel": {"bg": "#B8B8D0", "text": "#000"},
    "fairy": {"bg": "#EE99AC", "text": "#000"},
}

# Type gradients for cards
TYPE_GRADIENTS = {
    "normal": "linear-gradient(135deg, rgba(168,168,120,0.2), rgba(168,168,120,0.05))",
    "fire": "linear-gradient(135deg, rgba(240,128,48,0.2), rgba(240,128,48,0.05))",
    "water": "linear-gradient(135deg, rgba(104,144,240,0.2), rgba(104,144,240,0.05))",
    "electric": "linear-gradient(135deg, rgba(248,208,48,0.2), rgba(248,208,48,0.05))",
    "grass": "linear-gradient(135deg, rgba(120,200,80,0.2), rgba(120,200,80,0.05))",
    "ice": "linear-gradient(135deg, rgba(152,216,216,0.2), rgba(152,216,216,0.05))",
    "fighting": "linear-gradient(135deg, rgba(192,48,40,0.2), rgba(192,48,40,0.05))",
    "poison": "linear-gradient(135deg, rgba(160,64,160,0.2), rgba(160,64,160,0.05))",
    "ground": "linear-gradient(135deg, rgba(224,192,104,0.2), rgba(224,192,104,0.05))",
    "flying": "linear-gradient(135deg, rgba(168,144,240,0.2), rgba(168,144,240,0.05))",
    "psychic": "linear-gradient(135deg, rgba(248,88,136,0.2), rgba(248,88,136,0.05))",
    "bug": "linear-gradient(135deg, rgba(168,184,32,0.2), rgba(168,184,32,0.05))",
    "rock": "linear-gradient(135deg, rgba(184,160,56,0.2), rgba(184,160,56,0.05))",
    "ghost": "linear-gradient(135deg, rgba(112,88,152,0.2), rgba(112,88,152,0.05))",
    "dragon": "linear-gradient(135deg, rgba(112,56,248,0.2), rgba(112,56,248,0.05))",
    "dark": "linear-gradient(135deg, rgba(112,88,72,0.2), rgba(112,88,72,0.05))",
    "steel": "linear-gradient(135deg, rgba(184,184,208,0.2), rgba(184,184,208,0.05))",
    "fairy": "linear-gradient(135deg, rgba(238,153,172,0.2), rgba(238,153,172,0.05))",
}

# =============================================================================
# CSS COMPONENT CLASSES
# =============================================================================

COMPONENT_STYLES = """
/* ===== RESET & BASE ===== */
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: var(--font-family);
    font-size: var(--font-size-md);
    color: var(--text-primary);
    background: var(--bg-primary);
    line-height: 1.5;
}

/* ===== GLASS CARD ===== */
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border-radius: var(--radius-xl);
    border: 1px solid var(--glass-border);
    box-shadow: var(--shadow-lg), var(--shadow-inset);
    padding: var(--space-lg);
    position: relative;
    overflow: hidden;
    transition: all var(--duration-normal) var(--ease-smooth);
}

.glass-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
    transition: left 0.6s var(--ease-smooth);
    pointer-events: none;
}

.glass-card:hover {
    transform: translateY(-4px);
    border-color: var(--glass-border-hover);
    box-shadow: var(--shadow-xl), var(--glow-primary);
}

.glass-card:hover::before {
    left: 100%;
}

/* ===== GLASS CARD VARIANTS ===== */
.glass-card-success {
    border-color: rgba(34, 197, 94, 0.3);
}
.glass-card-success:hover {
    box-shadow: var(--shadow-xl), var(--glow-success);
}

.glass-card-danger {
    border-color: rgba(239, 68, 68, 0.3);
}
.glass-card-danger:hover {
    box-shadow: var(--shadow-xl), var(--glow-danger);
}

.glass-card-warning {
    border-color: rgba(245, 158, 11, 0.3);
}
.glass-card-warning:hover {
    box-shadow: var(--shadow-xl), var(--glow-warning);
}

/* ===== SPRITE CONTAINER ===== */
.sprite-container {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    animation: spriteEntrance 0.5s var(--ease-bounce);
}

.sprite-container img {
    image-rendering: pixelated;
    transition: transform var(--duration-normal) var(--ease-bounce);
}

.sprite-container:hover img {
    animation: spriteBounce 0.6s var(--ease-bounce);
}

/* ===== BUTTONS ===== */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    background: var(--glass-bg);
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    cursor: pointer;
    transition: all var(--duration-fast) var(--ease-smooth);
    outline: none;
}

.btn:hover {
    background: var(--glass-bg-hover);
    border-color: var(--glass-border-hover);
    transform: translateY(-2px);
}

.btn:active {
    transform: scale(0.98);
}

.btn-primary {
    background: var(--gradient-primary);
    border-color: transparent;
}

.btn-primary:hover {
    box-shadow: var(--glow-primary);
}

.btn-success {
    background: var(--gradient-success);
    border-color: transparent;
}

.btn-danger {
    background: var(--gradient-danger);
    border-color: transparent;
}

/* ===== TYPE BADGE ===== */
.type-badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-bold);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    box-shadow: var(--shadow-sm);
}

/* ===== KO BADGES ===== */
.ko-badge {
    display: inline-flex;
    align-items: center;
    padding: 6px 14px;
    border-radius: var(--radius-full);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-bold);
    animation: popIn 0.4s var(--ease-bounce);
}

.ko-badge.ohko {
    background: var(--gradient-danger);
    box-shadow: var(--glow-danger);
    animation: popIn 0.4s var(--ease-bounce), pulseGlowDanger 2s infinite 0.4s;
}

.ko-badge.twohko {
    background: var(--gradient-warning);
    box-shadow: var(--glow-warning);
}

.ko-badge.threehko {
    background: linear-gradient(135deg, #eab308 0%, #facc15 100%);
}

.ko-badge.survive {
    background: var(--gradient-success);
    box-shadow: var(--glow-success);
}

/* ===== DAMAGE BAR ===== */
.damage-bar-container {
    width: 100%;
    height: 28px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: var(--radius-full);
    overflow: hidden;
    position: relative;
}

.damage-bar {
    height: 100%;
    border-radius: var(--radius-full);
    background: linear-gradient(90deg, #22c55e 0%, #84cc16 30%, #f59e0b 60%, #ef4444 100%);
    background-size: 300% 100%;
    animation: damageFill 0.8s var(--ease-smooth) forwards;
    position: relative;
}

.damage-bar::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 50%;
    background: linear-gradient(to bottom, rgba(255,255,255,0.3), transparent);
    border-radius: var(--radius-full) var(--radius-full) 0 0;
}

.damage-text {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    font-weight: var(--font-weight-bold);
    font-size: var(--font-size-sm);
    text-shadow: 0 1px 3px rgba(0,0,0,0.5);
    animation: numberPop 0.5s var(--ease-bounce) 0.3s both;
}

/* ===== STAT BARS ===== */
.stat-bar-container {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin: var(--space-xs) 0;
}

.stat-label {
    width: 40px;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-bold);
    color: var(--text-secondary);
}

.stat-bar-track {
    flex: 1;
    height: 8px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: var(--radius-full);
    overflow: hidden;
}

.stat-bar-fill {
    height: 100%;
    border-radius: var(--radius-full);
    transform-origin: left;
    animation: statBarFill 0.6s var(--ease-smooth) forwards;
}

.stat-value {
    width: 35px;
    text-align: right;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    font-family: var(--font-mono);
}

/* ===== SKELETON LOADING ===== */
.skeleton {
    background: linear-gradient(90deg,
        rgba(255,255,255,0.05) 0%,
        rgba(255,255,255,0.1) 50%,
        rgba(255,255,255,0.05) 100%
    );
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: var(--radius-md);
}

.skeleton-text {
    height: 16px;
    margin: var(--space-xs) 0;
}

.skeleton-circle {
    border-radius: var(--radius-full);
}

/* ===== TABLES ===== */
.modern-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: var(--font-size-sm);
}

.modern-table th {
    background: rgba(99, 102, 241, 0.2);
    padding: var(--space-sm) var(--space-md);
    text-align: left;
    font-weight: var(--font-weight-medium);
    color: var(--text-secondary);
    border-bottom: 1px solid var(--glass-border);
}

.modern-table th:first-child {
    border-radius: var(--radius-md) 0 0 0;
}

.modern-table th:last-child {
    border-radius: 0 var(--radius-md) 0 0;
}

.modern-table td {
    padding: var(--space-sm) var(--space-md);
    background: var(--glass-bg);
    border-bottom: 1px solid var(--glass-border);
    transition: background var(--duration-fast);
}

.modern-table tr:hover td {
    background: var(--glass-bg-hover);
}

.modern-table tr:last-child td:first-child {
    border-radius: 0 0 0 var(--radius-md);
}

.modern-table tr:last-child td:last-child {
    border-radius: 0 0 var(--radius-md) 0;
}

/* ===== INPUTS ===== */
.input-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
}

.input-label {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.slider-input {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 8px;
    border-radius: var(--radius-full);
    background: rgba(255, 255, 255, 0.1);
    outline: none;
    transition: all var(--duration-fast);
}

.slider-input::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 20px;
    height: 20px;
    border-radius: var(--radius-full);
    background: var(--gradient-primary);
    cursor: pointer;
    box-shadow: var(--shadow-sm);
    transition: transform var(--duration-fast), box-shadow var(--duration-fast);
}

.slider-input::-webkit-slider-thumb:hover {
    transform: scale(1.2);
    box-shadow: var(--glow-primary);
}

.select-input {
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    background: var(--glass-bg);
    color: var(--text-primary);
    font-size: var(--font-size-sm);
    cursor: pointer;
    outline: none;
    transition: all var(--duration-fast);
}

.select-input:hover {
    border-color: var(--glass-border-hover);
}

.select-input:focus {
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

/* ===== GRID LAYOUTS ===== */
.grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-md);
}

.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-md);
}

.grid-6 {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: var(--space-sm);
}

/* ===== UTILITY CLASSES ===== */
.text-center { text-align: center; }
.text-right { text-align: right; }
.text-muted { color: var(--text-muted); }
.text-success { color: var(--accent-success); }
.text-danger { color: var(--accent-danger); }
.text-warning { color: var(--accent-warning); }

.flex { display: flex; }
.flex-center { display: flex; align-items: center; justify-content: center; }
.flex-between { display: flex; align-items: center; justify-content: space-between; }
.gap-sm { gap: var(--space-sm); }
.gap-md { gap: var(--space-md); }

.mt-sm { margin-top: var(--space-sm); }
.mt-md { margin-top: var(--space-md); }
.mt-lg { margin-top: var(--space-lg); }
.mb-sm { margin-bottom: var(--space-sm); }
.mb-md { margin-bottom: var(--space-md); }

.animate-fadeIn { animation: fadeIn var(--duration-normal) var(--ease-smooth); }
.animate-slideIn { animation: fadeSlideIn var(--duration-normal) var(--ease-smooth); }
.animate-popIn { animation: popIn var(--duration-normal) var(--ease-bounce); }

/* Staggered animations */
.stagger-1 { animation-delay: 0.05s; }
.stagger-2 { animation-delay: 0.1s; }
.stagger-3 { animation-delay: 0.15s; }
.stagger-4 { animation-delay: 0.2s; }
.stagger-5 { animation-delay: 0.25s; }
.stagger-6 { animation-delay: 0.3s; }
"""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_full_styles() -> str:
    """Get all CSS styles combined."""
    return f"<style>{DESIGN_TOKENS}{ANIMATIONS}{COMPONENT_STYLES}</style>"


def get_type_color(type_name: str) -> dict:
    """Get background and text color for a Pokemon type."""
    return TYPE_COLORS.get(type_name.lower(), {"bg": "#888", "text": "#fff"})


def get_type_gradient(type_name: str) -> str:
    """Get gradient background for a Pokemon type card."""
    return TYPE_GRADIENTS.get(type_name.lower(), "linear-gradient(135deg, rgba(136,136,136,0.2), rgba(136,136,136,0.05))")


def create_type_badge(type_name: str) -> str:
    """Create a type badge HTML element."""
    colors = get_type_color(type_name)
    return f'''<span class="type-badge" style="background:{colors['bg']};color:{colors['text']}">{type_name.upper()}</span>'''


def create_ko_badge(ko_chance: str) -> str:
    """Create a KO badge with appropriate styling."""
    ko_lower = ko_chance.lower()
    if "ohko" in ko_lower or "guaranteed" in ko_lower:
        css_class = "ohko"
    elif "2hko" in ko_lower:
        css_class = "twohko"
    elif "3hko" in ko_lower:
        css_class = "threehko"
    else:
        css_class = "survive"
    return f'<span class="ko-badge {css_class}">{ko_chance}</span>'


def create_damage_bar(percent: float, show_text: bool = True) -> str:
    """Create an animated damage bar."""
    # Clamp percent between 0 and 200 for display
    display_percent = min(200, max(0, percent))
    bar_width = min(100, display_percent)

    # Determine color based on damage
    if percent >= 100:
        bg_position = "100%"
    elif percent >= 50:
        bg_position = f"{percent}%"
    else:
        bg_position = "0%"

    text_html = f'<span class="damage-text">{percent:.1f}%</span>' if show_text else ''

    return f'''
    <div class="damage-bar-container">
        <div class="damage-bar" style="--damage-percent:{bar_width}%;background-position:{bg_position} 0"></div>
        {text_html}
    </div>
    '''


def create_stat_bar(stat_name: str, value: int, max_value: int = 255, color: Optional[str] = None) -> str:
    """Create an animated stat bar."""
    percent = (value / max_value) * 100

    # Default color gradient based on value
    if color is None:
        if percent >= 80:
            color = "var(--gradient-success)"
        elif percent >= 50:
            color = "var(--gradient-primary)"
        elif percent >= 30:
            color = "var(--gradient-warning)"
        else:
            color = "var(--gradient-danger)"

    return f'''
    <div class="stat-bar-container">
        <span class="stat-label">{stat_name}</span>
        <div class="stat-bar-track">
            <div class="stat-bar-fill" style="width:{percent}%;background:{color}"></div>
        </div>
        <span class="stat-value">{value}</span>
    </div>
    '''


def create_skeleton(width: str = "100%", height: str = "16px", variant: str = "text") -> str:
    """Create a skeleton loading placeholder."""
    extra_class = "skeleton-circle" if variant == "circle" else "skeleton-text"
    return f'<div class="skeleton {extra_class}" style="width:{width};height:{height}"></div>'


def get_sprite_url(pokemon_name: str, animated: bool = True) -> str:
    """Get Pokemon sprite URL from Showdown."""
    if animated:
        # Pokemon Showdown format: no spaces, forms use single hyphen
        # "Flutter Mane" -> "fluttermane"
        # "Urshifu-Rapid-Strike" -> "urshifu-rapidstrike"
        normalized = pokemon_name.lower().replace(" ", "").replace(".", "").replace("'", "")

        # Collapse form hyphens: "rapid-strike" -> "rapidstrike"
        # But keep the base-form hyphen: "urshifu-rapidstrike"
        parts = normalized.split("-")
        if len(parts) >= 2:
            base = parts[0]
            form = "".join(parts[1:])
            normalized = f"{base}-{form}" if form else base

        return f"https://play.pokemonshowdown.com/sprites/ani/{normalized}.gif"
    else:
        # Fallback static sprites
        normalized = pokemon_name.lower().replace(" ", "-").replace(".", "").replace("'", "")
        return f"https://play.pokemonshowdown.com/sprites/gen5/{normalized}.png"


def create_sprite_html(pokemon_name: str, size: int = 96, animated: bool = True) -> str:
    """Create a sprite image with fallback and animations."""
    primary_url = get_sprite_url(pokemon_name, animated)
    fallback_url = get_sprite_url(pokemon_name, False)

    return f'''
    <div class="sprite-container" style="width:{size}px;height:{size}px">
        <img src="{primary_url}"
             alt="{pokemon_name}"
             style="max-width:100%;max-height:100%"
             onerror="this.src='{fallback_url}';this.onerror=null;">
    </div>
    '''
