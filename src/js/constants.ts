import { defines } from "./struct_info_generated.json";

declare global {
  /** @private */
  export const cDefs: typeof defines;
  /** @private */
  export const DEBUG: boolean;
  /** @private */
  export const SOURCEMAP: boolean;
}
