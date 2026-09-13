import styles from './Meter.module.css'

export function Meter({ value, label }: { value: number; label?: string }) {
  const clamped = Math.max(0, Math.min(1, value))
  return (
    <div className={styles.wrap}>
      <div className={styles.track} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(clamped * 100)} aria-label={label}>
        <span className={styles.fill} style={{ width: `${clamped * 100}%` }} />
      </div>
      {label ? <span className={styles.label}>{label}</span> : null}
    </div>
  )
}
