# Predictive Analytics Visualization Guide

This guide provides examples for visualizing demand forecasts and stock optimization results in your frontend application.

## Forecast Chart Components

### React Component Example - Demand Forecast Chart

```tsx
// DemandForecastChart.tsx

import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, Area, AreaChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Brush
} from 'recharts';
import { format, parseISO } from 'date-fns';

interface ForecastPoint {
  timestamp: string;
  predicted_value: number;
  lower_bound?: number;
  upper_bound?: number;
  actual_value?: number;
}

interface DemandForecastChartProps {
  forecastData: ForecastPoint[];
  title: string;
  showConfidenceInterval?: boolean;
  showActuals?: boolean;
}

export const DemandForecastChart: React.FC<DemandForecastChartProps> = ({
  forecastData,
  title,
  showConfidenceInterval = true,
  showActuals = false
}) => {
  const [chartData, setChartData] = useState<any[]>([]);

  useEffect(() => {
    // Transform data for Recharts
    const transformedData = forecastData.map(point => ({
      date: format(parseISO(point.timestamp), 'MMM dd'),
      fullDate: point.timestamp,
      predicted: point.predicted_value,
      lowerBound: point.lower_bound,
      upperBound: point.upper_bound,
      actual: point.actual_value,
      confidenceRange: point.upper_bound && point.lower_bound
        ? [point.lower_bound, point.upper_bound]
        : undefined
    }));
    
    setChartData(transformedData);
  }, [forecastData]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-4 border rounded shadow-lg">
          <p className="font-semibold">{format(parseISO(data.fullDate), 'PPP')}</p>
          <p className="text-blue-600">
            Predicted: {data.predicted.toFixed(0)} units
          </p>
          {data.actual && (
            <p className="text-green-600">
              Actual: {data.actual.toFixed(0)} units
            </p>
          )}
          {showConfidenceInterval && data.lowerBound && (
            <p className="text-gray-500 text-sm">
              Range: {data.lowerBound.toFixed(0)} - {data.upperBound.toFixed(0)}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full h-96 bg-white p-4 rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <defs>
            <linearGradient id="colorPredicted" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0.1}/>
            </linearGradient>
            <linearGradient id="colorConfidence" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#9CA3AF" stopOpacity={0.3}/>
              <stop offset="95%" stopColor="#9CA3AF" stopOpacity={0.1}/>
            </linearGradient>
          </defs>
          
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          
          {/* Confidence interval area */}
          {showConfidenceInterval && (
            <Area
              type="monotone"
              dataKey="confidenceRange"
              stroke="none"
              fill="url(#colorConfidence)"
              name="Confidence Interval"
            />
          )}
          
          {/* Predicted line */}
          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#3B82F6"
            strokeWidth={3}
            dot={{ r: 4 }}
            name="Predicted"
          />
          
          {/* Actual line */}
          {showActuals && (
            <Line
              type="monotone"
              dataKey="actual"
              stroke="#10B981"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={{ r: 3 }}
              name="Actual"
            />
          )}
          
          {/* Today marker */}
          <ReferenceLine
            x={format(new Date(), 'MMM dd')}
            stroke="#EF4444"
            strokeDasharray="3 3"
            label="Today"
          />
          
          <Brush dataKey="date" height={30} stroke="#3B82F6" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
```

### Stock Optimization Dashboard

```tsx
// StockOptimizationDashboard.tsx

import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, RadialBarChart,
  RadialBar, ScatterChart, Scatter
} from 'recharts';

interface StockRecommendation {
  product_id: number;
  product_name: string;
  current_stock: number;
  recommended_stock: number;
  reorder_point: number;
  safety_stock: number;
  expected_stockout_risk: number;
}

interface StockOptimizationDashboardProps {
  recommendations: StockRecommendation[];
  totalInvestment: number;
  expectedServiceLevel: number;
}

export const StockOptimizationDashboard: React.FC<StockOptimizationDashboardProps> = ({
  recommendations,
  totalInvestment,
  expectedServiceLevel
}) => {
  // Prepare data for different charts
  const stockComparisonData = recommendations.map(rec => ({
    name: rec.product_name.substring(0, 15) + '...',
    current: rec.current_stock,
    recommended: rec.recommended_stock,
    difference: rec.recommended_stock - rec.current_stock
  }));

  const riskData = recommendations.map(rec => ({
    name: rec.product_name,
    risk: rec.expected_stockout_risk * 100,
    safetyStock: rec.safety_stock
  }));

  const getStockStatusColor = (current: number, recommended: number) => {
    const ratio = current / recommended;
    if (ratio < 0.5) return '#EF4444'; // Red - Critical
    if (ratio < 0.8) return '#F59E0B'; // Amber - Low
    if (ratio > 1.2) return '#6B7280'; // Gray - Overstock
    return '#10B981'; // Green - Optimal
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Key Metrics */}
      <div className="col-span-2 grid grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <h4 className="text-sm font-medium text-gray-500">Total Investment Required</h4>
          <p className="text-2xl font-bold text-blue-600">${totalInvestment.toLocaleString()}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h4 className="text-sm font-medium text-gray-500">Expected Service Level</h4>
          <p className="text-2xl font-bold text-green-600">{(expectedServiceLevel * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h4 className="text-sm font-medium text-gray-500">Products Optimized</h4>
          <p className="text-2xl font-bold text-purple-600">{recommendations.length}</p>
        </div>
      </div>

      {/* Stock Comparison Chart */}
      <div className="bg-white p-4 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Current vs Recommended Stock</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={stockComparisonData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
            <YAxis />
            <Tooltip />
            <Bar dataKey="current" fill="#6B7280" name="Current Stock" />
            <Bar dataKey="recommended" fill="#3B82F6" name="Recommended Stock" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Stockout Risk Chart */}
      <div className="bg-white p-4 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Stockout Risk Analysis</h3>
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="safetyStock" name="Safety Stock" />
            <YAxis dataKey="risk" name="Stockout Risk (%)" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter
              name="Products"
              data={riskData}
              fill="#8884d8"
            >
              {riskData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.risk > 10 ? '#EF4444' : entry.risk > 5 ? '#F59E0B' : '#10B981'}
                />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Stock Status Distribution */}
      <div className="bg-white p-4 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Stock Status Distribution</h3>
        <div className="space-y-4">
          {recommendations.slice(0, 10).map((rec, idx) => {
            const ratio = rec.current_stock / rec.recommended_stock;
            const percentage = Math.min(ratio * 100, 150);
            const color = getStockStatusColor(rec.current_stock, rec.recommended_stock);
            
            return (
              <div key={idx}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">{rec.product_name}</span>
                  <span>{percentage.toFixed(0)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="h-2 rounded-full transition-all duration-500"
                    style={{
                      width: `${percentage}%`,
                      backgroundColor: color
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Reorder Points Chart */}
      <div className="bg-white p-4 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Reorder Points</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={recommendations.slice(0, 8)}
            layout="horizontal"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="product_name" type="category" width={90} />
            <Tooltip />
            <Bar dataKey="reorder_point" fill="#F59E0B" name="Reorder Point" />
            <Bar dataKey="safety_stock" fill="#3B82F6" name="Safety Stock" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
```

### Real-time Prediction Updates Component

```tsx
// PredictionUpdatesPanel.tsx

import React, { useEffect, useState } from 'react';
import { AlertCircle, TrendingUp, Package, Zap } from 'lucide-react';

interface PredictionUpdate {
  update_id: string;
  update_type: 'forecast_update' | 'alert' | 'insight';
  entity_type: string;
  data: any;
  timestamp: string;
}

export const PredictionUpdatesPanel: React.FC = () => {
  const [updates, setUpdates] = useState<PredictionUpdate[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSocket for real-time updates
    const websocket = new WebSocket('ws://localhost:8000/analytics/predictive/ws');
    
    websocket.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setUpdates(prev => [update, ...prev].slice(0, 20)); // Keep last 20 updates
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, []);

  const getUpdateIcon = (type: string) => {
    switch (type) {
      case 'alert':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'insight':
        return <Zap className="w-5 h-5 text-yellow-500" />;
      case 'forecast_update':
        return <TrendingUp className="w-5 h-5 text-blue-500" />;
      default:
        return <Package className="w-5 h-5 text-gray-500" />;
    }
  };

  const getUpdateColor = (type: string) => {
    switch (type) {
      case 'alert':
        return 'border-red-200 bg-red-50';
      case 'insight':
        return 'border-yellow-200 bg-yellow-50';
      case 'forecast_update':
        return 'border-blue-200 bg-blue-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold mb-4">Real-time Predictions</h3>
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {updates.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No updates yet...</p>
        ) : (
          updates.map((update) => (
            <div
              key={update.update_id}
              className={`p-3 rounded-lg border ${getUpdateColor(update.update_type)}`}
            >
              <div className="flex items-start gap-3">
                {getUpdateIcon(update.update_type)}
                <div className="flex-1">
                  <div className="flex justify-between items-start">
                    <h4 className="font-medium text-sm">
                      {update.data.title || update.data.entity_name || 'Update'}
                    </h4>
                    <span className="text-xs text-gray-500">
                      {new Date(update.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">
                    {update.data.message || update.data.description || 'New prediction available'}
                  </p>
                  {update.data.recommended_actions && (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-gray-700">Recommended Actions:</p>
                      <ul className="text-xs text-gray-600 mt-1 space-y-1">
                        {update.data.recommended_actions.slice(0, 2).map((action: any, idx: number) => (
                          <li key={idx} className="flex items-center gap-1">
                            <span className="w-1 h-1 bg-gray-400 rounded-full" />
                            {typeof action === 'string' ? action : action.description}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
```

### Forecast Accuracy Monitor

```tsx
// ForecastAccuracyMonitor.tsx

import React from 'react';
import { RadialBarChart, RadialBar, Legend, ResponsiveContainer, PolarAngleAxis } from 'recharts';

interface AccuracyMetrics {
  mae: number;
  mape: number;
  rmse: number;
  r_squared: number;
}

interface ForecastAccuracyMonitorProps {
  metrics: AccuracyMetrics;
  modelType: string;
}

export const ForecastAccuracyMonitor: React.FC<ForecastAccuracyMonitorProps> = ({
  metrics,
  modelType
}) => {
  const accuracy = 100 - metrics.mape;
  
  const data = [{
    name: 'Accuracy',
    value: accuracy,
    fill: accuracy > 80 ? '#10B981' : accuracy > 60 ? '#F59E0B' : '#EF4444'
  }];

  const getAccuracyLabel = (acc: number) => {
    if (acc > 80) return 'Excellent';
    if (acc > 70) return 'Good';
    if (acc > 60) return 'Fair';
    return 'Poor';
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-2">{modelType} Model Accuracy</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <ResponsiveContainer width="100%" height={200}>
            <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={data}>
              <PolarAngleAxis
                type="number"
                domain={[0, 100]}
                angleAxisId={0}
                tick={false}
              />
              <RadialBar
                dataKey="value"
                cornerRadius={10}
                fill={data[0].fill}
              />
              <text
                x="50%"
                y="50%"
                textAnchor="middle"
                dominantBaseline="middle"
                className="text-3xl font-bold"
              >
                {accuracy.toFixed(0)}%
              </text>
              <text
                x="50%"
                y="60%"
                textAnchor="middle"
                dominantBaseline="middle"
                className="text-sm text-gray-600"
              >
                {getAccuracyLabel(accuracy)}
              </text>
            </RadialBarChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-3">
          <div>
            <p className="text-xs text-gray-500">Mean Absolute Error</p>
            <p className="text-lg font-semibold">{metrics.mae.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">RMSE</p>
            <p className="text-lg font-semibold">{metrics.rmse.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">R-squared</p>
            <p className="text-lg font-semibold">{metrics.r_squared.toFixed(3)}</p>
          </div>
        </div>
      </div>
    </div>
  );
};
```

## Integration Examples

### Fetching Forecast Data

```typescript
// api/predictions.ts

export const fetchDemandForecast = async (
  entityType: string,
  entityId: number,
  horizonDays: number = 7
) => {
  const response = await fetch('/api/analytics/predictive/demand-forecast', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: JSON.stringify({
      entity_type: entityType,
      entity_id: entityId,
      horizon_days: horizonDays,
      include_confidence_intervals: true
    })
  });

  if (!response.ok) {
    throw new Error('Failed to fetch forecast');
  }

  return response.json();
};

export const optimizeStock = async (
  productIds: number[],
  serviceLevel: number = 0.95
) => {
  const response = await fetch('/api/analytics/predictive/stock-optimization', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: JSON.stringify({
      product_ids: productIds,
      service_level: serviceLevel,
      optimization_objective: 'balanced',
      include_safety_stock: true
    })
  });

  return response.json();
};
```

### Complete Dashboard Example

```tsx
// PredictiveAnalyticsDashboard.tsx

import React, { useState, useEffect } from 'react';
import { DemandForecastChart } from './DemandForecastChart';
import { StockOptimizationDashboard } from './StockOptimizationDashboard';
import { PredictionUpdatesPanel } from './PredictionUpdatesPanel';
import { ForecastAccuracyMonitor } from './ForecastAccuracyMonitor';
import { fetchDemandForecast, optimizeStock } from './api/predictions';

export const PredictiveAnalyticsDashboard: React.FC = () => {
  const [selectedProduct, setSelectedProduct] = useState<number | null>(null);
  const [forecastData, setForecastData] = useState(null);
  const [stockData, setStockData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedProduct) {
      loadForecastData(selectedProduct);
    }
  }, [selectedProduct]);

  const loadForecastData = async (productId: number) => {
    setLoading(true);
    try {
      const [forecast, optimization] = await Promise.all([
        fetchDemandForecast('product', productId, 14),
        optimizeStock([productId])
      ]);
      
      setForecastData(forecast);
      setStockData(optimization);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Predictive Analytics Dashboard</h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {forecastData && (
            <DemandForecastChart
              forecastData={forecastData.predictions}
              title={`Demand Forecast - ${forecastData.entity_name}`}
              showConfidenceInterval={true}
            />
          )}
        </div>
        
        <div>
          <PredictionUpdatesPanel />
        </div>
      </div>

      {stockData && (
        <StockOptimizationDashboard
          recommendations={stockData.recommendations}
          totalInvestment={stockData.total_investment_required}
          expectedServiceLevel={stockData.expected_service_level}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <ForecastAccuracyMonitor
          metrics={{
            mae: 5.2,
            mape: 12.3,
            rmse: 7.8,
            r_squared: 0.85
          }}
          modelType="Ensemble"
        />
      </div>
    </div>
  );
};
```

## Styling with Tailwind CSS

```css
/* Add to your global styles */
.forecast-chart-container {
  @apply bg-white rounded-lg shadow-md p-4;
}

.forecast-tooltip {
  @apply bg-white p-3 rounded shadow-lg border border-gray-200;
}

.metric-card {
  @apply bg-white p-6 rounded-lg shadow hover:shadow-lg transition-shadow;
}

.alert-card {
  @apply p-4 rounded-lg border-l-4;
}

.alert-card.critical {
  @apply bg-red-50 border-red-500 text-red-800;
}

.alert-card.warning {
  @apply bg-yellow-50 border-yellow-500 text-yellow-800;
}

.alert-card.info {
  @apply bg-blue-50 border-blue-500 text-blue-800;
}
```

## Best Practices

1. **Performance Optimization**
   - Use React.memo for chart components
   - Implement data pagination for large datasets
   - Use WebSocket connections for real-time updates

2. **Responsive Design**
   - Ensure charts are responsive
   - Use grid layouts that adapt to screen sizes
   - Provide mobile-friendly alternatives

3. **Accessibility**
   - Add ARIA labels to charts
   - Provide text alternatives for visual data
   - Ensure keyboard navigation

4. **Error Handling**
   - Show loading states during data fetching
   - Display meaningful error messages
   - Provide fallback UI for failed requests

This visualization guide provides a comprehensive foundation for implementing predictive analytics visualizations in your frontend application.