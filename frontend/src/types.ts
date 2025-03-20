/**
 * Typed representations of the RAG Quality Monitor backend contract.
 *
 * The model is split in two:
 *  - `model/domain.ts` — the persisted domain entities (projects, apps, datasets,
 *    runs, results, gate policies, providers …).
 *  - `model/api.ts` — the composite API payloads (overview, compare, drift,
 *    system info, validation reports …).
 *
 * Field names mirror the JSON exactly so responses can be used without mapping.
 */
export * from './model/domain'
export * from './model/api'
