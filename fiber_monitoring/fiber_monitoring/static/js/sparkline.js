// Animated Sparkline Chart Generator
class SparklineChart {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.data = [];
        this.maxPoints = options.maxPoints || 60;
        this.animating = true;
        this.severity = 'healthy'; // healthy, warning, critical
        
        // Set canvas size
        this.canvas.width = options.width || 300;
        this.canvas.height = options.height || 80;
        
        // Colors based on severity
        this.colors = {
            healthy: '#00d4ff',
            warning: '#ff9500',
            critical: '#ff006e'
        };
        
        this.initializeData();
        this.animate();
    }
    
    initializeData() {
        this.data = [];
        for (let i = 0; i < this.maxPoints; i++) {
            this.data.push(Math.random() * 80 + 20);
        }
    }
    
    addDataPoint(value) {
        this.data.push(value);
        if (this.data.length > this.maxPoints) {
            this.data.shift();
        }
        
        // Update severity
        if (value > 85) {
            this.severity = 'critical';
        } else if (value > 70) {
            this.severity = 'warning';
        } else {
            this.severity = 'healthy';
        }
    }
    
    draw() {
        const { width, height } = this.canvas;
        const padding = 10;
        const graphWidth = width - padding * 2;
        const graphHeight = height - padding * 2;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, width, height);
        
        if (this.data.length < 2) return;
        
        // Draw grid
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        this.ctx.lineWidth = 1;
        for (let i = 0; i <= 5; i++) {
            const y = padding + (graphHeight / 5) * i;
            this.ctx.beginPath();
            this.ctx.moveTo(padding, y);
            this.ctx.lineTo(width - padding, y);
            this.ctx.stroke();
        }
        
        // Draw data line
        const minVal = Math.min(...this.data);
        const maxVal = Math.max(...this.data);
        const range = maxVal - minVal || 1;
        
        // Gradient fill
        const gradient = this.ctx.createLinearGradient(0, padding, 0, height - padding);
        gradient.addColorStop(0, this.colors[this.severity] + '40');
        gradient.addColorStop(1, this.colors[this.severity] + '00');
        
        this.ctx.fillStyle = gradient;
        this.ctx.strokeStyle = this.colors[this.severity];
        this.ctx.lineWidth = 2;
        
        // Draw path
        this.ctx.beginPath();
        this.data.forEach((value, index) => {
            const x = padding + (index / (this.data.length - 1)) * graphWidth;
            const y = height - padding - ((value - minVal) / range) * graphHeight;
            
            if (index === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        });
        
        this.ctx.stroke();
        
        // Fill area
        this.ctx.lineTo(width - padding, height - padding);
        this.ctx.lineTo(padding, height - padding);
        this.ctx.closePath();
        this.ctx.fill();
        
        // Draw cursor point
        const lastValue = this.data[this.data.length - 1];
        const lastX = width - padding;
        const lastY = height - padding - ((lastValue - minVal) / range) * graphHeight;
        
        this.ctx.fillStyle = this.colors[this.severity];
        this.ctx.beginPath();
        this.ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Glow effect
        this.ctx.strokeStyle = this.colors[this.severity] + '80';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        this.ctx.arc(lastX, lastY, 6, 0, Math.PI * 2);
        this.ctx.stroke();
    }
    
    animate() {
        this.draw();
        
        if (this.animating) {
            requestAnimationFrame(() => this.animate());
        }
    }
    
    updateSeverity(severity) {
        this.severity = severity;
    }
    
    destroy() {
        this.animating = false;
    }
}

// Global sparkline instances
const sparklines = {};

function initSparklines() {
    const chartIds = ['chart-cpu', 'chart-network', 'chart-latency'];
    
    chartIds.forEach(id => {
        sparklines[id] = new SparklineChart(id, {
            width: 280,
            height: 70,
            maxPoints: 50
        });
    });
    
    // Simulate real-time data updates
    setInterval(() => {
        Object.keys(sparklines).forEach(key => {
            const value = Math.random() * 100;
            sparklines[key].addDataPoint(value);
        });
    }, 500);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initSparklines);
