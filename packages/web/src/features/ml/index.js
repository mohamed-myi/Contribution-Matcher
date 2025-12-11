/**
 * ML Feature Module
 * 
 * Handles machine learning:
 * - Issue labeling for training
 * - Model training
 * - Model status
 */

// Components
export { default as MLTrainingPage } from './components/MLTrainingPage';
export { default as LabelingUI } from './components/LabelingUI';
export { default as ModelStatus } from './components/ModelStatus';

// Hooks
export { useLabeling } from './hooks/useLabeling';
export { useModelStatus } from './hooks/useModelStatus';
export { useTrainModel } from './hooks/useTrainModel';

// Services
export { mlService } from './services/mlService';
