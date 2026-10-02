import type { MouseEvent } from 'react'
import {
  Card,
  CardContent,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'

const PRESETS = [7, 30, 90] as const

export interface FilterBarProps {
  dateFrom: string
  dateTo: string
  onDateFromChange: (value: string) => void
  onDateToChange: (value: string) => void
  categories: string[]
  category: string
  onCategoryChange: (value: string) => void
}

// Fechas ISO-8601 locales (YYYY-MM-DD) a partir de las partes locales.
function toIsoLocal(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function presetRange(days: number): { from: string; to: string } {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - (days - 1))
  return { from: toIsoLocal(from), to: toIsoLocal(to) }
}

export default function FilterBar({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  categories,
  category,
  onCategoryChange,
}: FilterBarProps) {
  const activePreset =
    PRESETS.find((days) => {
      const range = presetRange(days)
      return range.from === dateFrom && range.to === dateTo
    }) ?? null

  const handlePreset = (_event: MouseEvent<HTMLElement>, value: number | null) => {
    if (value === null) return
    const range = presetRange(value)
    onDateFromChange(range.from)
    onDateToChange(range.to)
  }

  const handleDateFrom = (value: string) => {
    onDateFromChange(value)
  }

  const handleDateTo = (value: string) => {
    onDateToChange(value)
  }

  return (
    <Card
      variant="outlined"
      sx={{ borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
    >
      <CardContent>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={2}
          useFlexGap
          sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
        >
          <ToggleButtonGroup
            size="small"
            exclusive
            value={activePreset}
            onChange={handlePreset}
          >
            {PRESETS.map((days) => (
              <ToggleButton key={days} value={days}>
                {days} días
              </ToggleButton>
            ))}
          </ToggleButtonGroup>

          <TextField
            label="Desde"
            type="date"
            size="small"
            value={dateFrom}
            onChange={(event) => handleDateFrom(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />

          <TextField
            label="Hasta"
            type="date"
            size="small"
            value={dateTo}
            onChange={(event) => handleDateTo(event.target.value)}
            slotProps={{ inputLabel: { shrink: true } }}
          />

          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel id="filter-category-label">Categoría</InputLabel>
            <Select
              labelId="filter-category-label"
              label="Categoría"
              value={category}
              onChange={(event) => onCategoryChange(event.target.value)}
            >
              <MenuItem value="">Todas</MenuItem>
              {categories.map((item) => (
                <MenuItem key={item} value={item}>
                  {item}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </CardContent>
    </Card>
  )
}
