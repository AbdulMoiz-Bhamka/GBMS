// HTML pattern is compiled with the RegExp v flag in modern browsers.
// Express the hyphen as a hex escape so the character class is valid in v mode.
export const SKU_PATTERN = String.raw`[A-Za-z0-9][A-Za-z0-9._\/\-]{0,59}`
