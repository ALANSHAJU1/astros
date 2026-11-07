import {
  Binoculars,
  Camera,
  Eye,
  Layers,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Telescope,
} from "lucide-react";

export default function ExploreFilters({
  categories,
  activeCategory,
  onCategoryChange,
  search,
  onSearchChange,
  sourceFilter = "all", // "all", "predicted", "database"
  onSourceFilterChange,
  equipmentFilter = "all", // "all", "eye", "binoculars", "telescope", "sun", "camera"
  onEquipmentFilterChange,
  onPredictClick,
  predicting = false,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}) {
  return (
    <section className="explore-controls">
      {/* Top row: Search + Source Selector + Predict Button */}
      <div className="explore-search-row">
        <div className="explore-search">
          <Search size={18} />
          <input
            type="search"
            placeholder="Search planets, eclipses, comets, asteroids, meteor showers, deep sky..."
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

        {/* Source Filter Selector: Allows choosing Database vs Predicted vs All */}
        <div className="source-filter-group" role="group" aria-label="Event Source Selection">
          <button
            className={`source-chip ${sourceFilter === "all" ? "active" : ""}`}
            onClick={() => onSourceFilterChange && onSourceFilterChange("all")}
            title="Display both database and live predicted events"
          >
            <Layers size={13} />
            <span>All Objects</span>
          </button>
          <button
            className={`source-chip ${sourceFilter === "predicted" ? "active" : ""}`}
            onClick={() => onSourceFilterChange && onSourceFilterChange("predicted")}
            title="Display celestial bodies predicted by AstroOS Intelligence"
          >
            <Sparkles size={13} />
            <span>Predicted Events</span>
          </button>
          <button
            className={`source-chip ${sourceFilter === "database" ? "active" : ""}`}
            onClick={() => onSourceFilterChange && onSourceFilterChange("database")}
            title="Display records saved in database"
          >
            <Eye size={13} />
            <span>Database Events</span>
          </button>
        </div>

        {/* Predict Action Button */}
        {onPredictClick && (
          <button
            className="predict-trigger-btn"
            onClick={onPredictClick}
            disabled={predicting}
            title="Predict observation passes for planets, comets, asteroids, and meteor showers"
          >
            {predicting ? (
              <RefreshCw size={14} className="loading-spinner" />
            ) : (
              <Sparkles size={14} />
            )}
            <span>{predicting ? "Predicting..." : "Predict Sky"}</span>
          </button>
        )}
      </div>

      {dateFrom !== undefined && (
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
      )}

      {/* Optical Equipment & Viewing Aid Selector */}
      <div className="equipment-filter-row">
        <div className="equipment-filter-label">
          <Telescope size={14} />
          <span>OPTICAL EQUIPMENT</span>
        </div>
        <div className="equipment-chip-group" role="group" aria-label="Filter by optical observation aid">
          <button
            className={`equipment-filter-chip ${equipmentFilter === "all" ? "active" : ""}`}
            onClick={() => onEquipmentFilterChange && onEquipmentFilterChange("all")}
          >
            <span>All Gear</span>
          </button>
          <button
            className={`equipment-filter-chip ${equipmentFilter === "eye" ? "active" : ""}`}
            onClick={() => onEquipmentFilterChange && onEquipmentFilterChange("eye")}
          >
            <Eye size={13} />
            <span>Naked Eye</span>
          </button>
          <button
            className={`equipment-filter-chip ${equipmentFilter === "binoculars" ? "active" : ""}`}
            onClick={() => onEquipmentFilterChange && onEquipmentFilterChange("binoculars")}
          >
            <Binoculars size={13} />
            <span>Binoculars</span>
          </button>
          <button
            className={`equipment-filter-chip ${equipmentFilter === "telescope" ? "active" : ""}`}
            onClick={() => onEquipmentFilterChange && onEquipmentFilterChange("telescope")}
          >
            <Telescope size={13} />
            <span>Telescope</span>
          </button>
          <button
            className={`equipment-filter-chip ${equipmentFilter === "sun" ? "active" : ""}`}
            onClick={() => onEquipmentFilterChange && onEquipmentFilterChange("sun")}
          >
            <Sun size={13} />
            <span>Solar Filter</span>
          </button>
          <button
            className={`equipment-filter-chip ${equipmentFilter === "camera" ? "active" : ""}`}
            onClick={() => onEquipmentFilterChange && onEquipmentFilterChange("camera")}
          >
            <Camera size={13} />
            <span>Astrophotography</span>
          </button>
        </div>
      </div>

      {/* Category Heading & Filter Chips */}
      <div className="category-heading">
        <div>
          <SlidersHorizontal size={15} />
          <span>FILTER BY CELESTIAL CATEGORY</span>
        </div>
        <span className="catalogue-label">
          {sourceFilter === "predicted"
            ? "PREDICTED CELESTIAL TARGETS"
            : sourceFilter === "database"
            ? "DATABASE CATALOGUE"
            : "ALL CELESTIAL TARGETS"}
        </span>
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
