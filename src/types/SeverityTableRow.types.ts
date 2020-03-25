
export interface SeverityTableRow {
  id: number
  ageGroup: string
  confirmed: number
  severe: number
  critical: number
  fatal: number
  totalFatal?: number
  isolated?: number
  errors?: {
    confirmed?: string
    severe?: string
    critical?: string
    fatal?: string
    isolated?: string
  }
}