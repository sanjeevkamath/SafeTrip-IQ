import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

console.log('Supabase Client Initialized:', { url: supabaseUrl?.substring(0, 30) + '...', hasKey: !!supabaseKey })

export const supabase = createClient(supabaseUrl, supabaseKey)
