import Image from 'next/image'
import styles from './AtlanticSand.module.css'

export default function BrandWordmark() {
    return <span className={styles.wordmark}>
        <Image src="/brand/mark.png" alt="" width={28} height={28} />
        <span>SafeTrip <span className={styles.wordmarkAccent}>IQ</span></span>
    </span>
}
