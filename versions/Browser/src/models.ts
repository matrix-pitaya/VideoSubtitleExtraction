import small from './small-model-manifest.json';
import medium from './medium-model-manifest.json';

export const MODELS = { small, medium };
export type ModelProfile = keyof typeof MODELS;
