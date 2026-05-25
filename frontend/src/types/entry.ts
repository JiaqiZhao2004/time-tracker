export type Entry = {
  id: string
  categoryId: string
  timestamp: string
}

export type DisplayEntry = Entry & {
  categoryName: string
}
