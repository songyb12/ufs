import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
process.chdir(dirname(fileURLToPath(import.meta.url)))
import('./node_modules/vite/bin/vite.js')
