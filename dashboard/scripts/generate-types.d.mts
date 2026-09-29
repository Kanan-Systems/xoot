// Types for generate-types.mjs, which runs under plain Node and is imported
// by the drift test.
export declare const SCHEMA_PATH: string;
export declare const TYPES_PATH: string;
export declare function generateTypes(schemaText: string): Promise<string>;
