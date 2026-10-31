import { Search, SlidersHorizontal } from "lucide-react";

export default function ExploreFilters({
  categories,
  activeCategory,
  onCategoryChange,
  search,
  onSearchChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}) {
  return (
    <section className="explore-controls">
      <div className="explore-search">
        <Search size={18} />
        <input
          type="search"
          placeholder="Search names, categories, event types..."
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label="Search celestial events"
        />
        {search && (
          <button
            className="search-clear"
            onClick={() => onSearchChange("")}
            aria-label="Clear search"
          >
            ×
          </button>
        )}
      </div>

      <div className="date-filters">
        <label>
          From
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => onDateFromChange(event.target.value)}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={dateTo}
            onChange={(event) => onDateToChange(event.target.value)}
          />
        </label>
      </div>

      <div className="category-heading">
        <div>
          <SlidersHorizontal size={15} />
          <span>EXPLORE BY CATEGORY</span>
        </div>
        <span className="catalogue-label">DATABASE EVENTS</span>
      </div>

      <div className="category-list" role="group" aria-label="Event categories">
        {categories.map((category) => (
          <button
            key={category}
            className={`category-chip ${
              activeCategory === category ? "selected" : ""
            }`}
            onClick={() => onCategoryChange(category)}
            aria-pressed={activeCategory === category}
          >
            {category}
          </button>
        ))}
      </div>
    </section>
  );
}
