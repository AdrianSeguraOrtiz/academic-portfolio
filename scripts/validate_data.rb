#!/usr/bin/env ruby
# frozen_string_literal: true

require "yaml"
require "pathname"

DATA_DIR = File.expand_path("../data", __dir__)
FILES = Dir[File.join(DATA_DIR, "**", "*.yaml")].sort

REFERENCE_PREFIXES = {
  "organization_ids" => "organization_",
  "degree_ids" => "degree_",
  "position_ids" => "position_",
  "current_position_ids" => "position_",
  "stay_ids" => "stay_",
  "current_stay_ids" => "stay_",
  "publication_ids" => "publication_",
  "publication_id" => "publication_",
  "software_project_ids" => "software_",
  "software_project_id" => "software_",
  "software_package_ids" => "package_",
  "research_project_ids" => "research_project_",
  "award_ids" => "award_",
  "grant_ids" => "grant_",
  "certification_ids" => "certification_",
  "course_ids" => "course_"
}.freeze

GROUP_REFERENCE_FIELDS = {
  "activities/dissemination/scientific_dissemination_articles.yaml" => {
    "scientific_dissemination_articles" => %w[
      publication_ids software_package_ids
    ]
  },
  "activities/dissemination/presentations.yaml" => {
    "presentations" => %w[
      publication_ids software_package_ids
    ]
  },
  "activities/dissemination/press.yaml" => {
    "press_items" => %w[
      publication_ids
    ]
  },
  "activities/dissemination/social_media.yaml" => {
    "social_media_items" => %w[
      publication_ids
    ]
  },
  "activities/dissemination/tv_media.yaml" => {
    "tv_items" => %w[
      publication_ids
    ]
  },
  "activities/teaching/university_classes.yaml" => {
    "university_classes" => %w[
      organization_ids
    ]
  },
  "activities/teaching/academic_supervision.yaml" => {
    "academic_supervision" => %w[
      organization_ids
    ]
  },
  "activities/teaching/teaching_innovation_projects.yaml" => {
    "teaching_innovation_projects" => %w[
      organization_ids
    ]
  },
  "career/honors.yaml" => {
    "honors" => %w[degree_ids]
  },
  "career/grants.yaml" => {
    "grants" => %w[position_ids stay_ids]
  },
  "career/degrees.yaml" => {
    "degrees" => %w[organization_ids grant_ids]
  },
  "career/certifications.yaml" => {
    "certifications" => %w[organization_ids]
  },
  "career/experience.yaml" => {
    "positions" => %w[organization_ids]
  },
  "career/research_stays.yaml" => {
    "stays" => %w[organization_ids grant_ids]
  },
  "research/publications.yaml" => {
    "journal_papers" => %w[
      organization_ids software_project_ids research_project_ids position_ids stay_ids grant_ids
    ],
    "conference_papers" => %w[
      organization_ids software_project_ids research_project_ids position_ids stay_ids grant_ids
    ]
  },
  "research/research_projects.yaml" => {
    "funded_projects" => %w[organization_ids]
  },
  "research/reviewing.yaml" => {
    "reviewing" => []
  },
  "research/software_packages.yaml" => {
    "software_packages" => []
  },
  "research/software_projects.yaml" => {
    "projects" => []
  }
}.freeze

DATE_CHECKS = {
  "career/degrees.yaml" => { "degrees" => "date_awarded" },
  "career/certifications.yaml" => { "certifications" => "issue_date" },
  "career/experience.yaml" => { "positions" => "start_date" },
  "career/research_stays.yaml" => { "stays" => "start_date" },
  "career/honors.yaml" => { "honors" => "issue_date" },
  "career/grants.yaml" => { "grants" => "issue_date" },
  "research/software_packages.yaml" => { "software_packages" => "id" },
  "research/research_projects.yaml" => { "funded_projects" => "start_date" },
  "research/reviewing.yaml" => { "reviewing" => "last_updated" },
  "activities/teaching/university_classes.yaml" => { "university_classes" => "start_date" },
  "activities/teaching/academic_supervision.yaml" => { "academic_supervision" => "date" },
  "activities/teaching/teaching_innovation_projects.yaml" => { "teaching_innovation_projects" => "start_date" },
  "activities/dissemination/presentations.yaml" => { "presentations" => "start_date" },
  "activities/dissemination/press.yaml" => { "press_items" => "date" },
  "activities/dissemination/social_media.yaml" => { "social_media_items" => "id" },
  "activities/dissemination/tv_media.yaml" => { "tv_items" => "date" },
  "activities/dissemination/scientific_dissemination_articles.yaml" => { "scientific_dissemination_articles" => "date" },
  "research/publications.yaml" => {
    "journal_papers" => "publication_date",
    "conference_papers" => "publication_date"
  }
}.freeze

def fail_with(message)
  warn(message)
  exit 1
end

data = FILES.to_h do |file|
  [Pathname.new(file).relative_path_from(Pathname.new(DATA_DIR)).to_s, YAML.load_file(file)]
rescue Psych::SyntaxError => e
  fail_with("Invalid YAML in #{file}: #{e.message}")
end

data.each do |file, document|
  next unless document.is_a?(Hash)

  document.each do |group, value|
    next unless value.is_a?(Array)
    next if value.empty? || !value.all? { |item| item.is_a?(Hash) }

    key_sets = value.map(&:keys).uniq
    next if key_sets.length == 1

    fail_with("#{file}: #{group} has inconsistent item fields")
  end
end

data.each do |file, document|
  next unless document.is_a?(Hash)

  document.each do |group, value|
    next unless value.is_a?(Array)
    next if value.empty? || !value.all? { |item| item.is_a?(Hash) }

    allowed_fields = GROUP_REFERENCE_FIELDS.dig(file, group) || []

    value.each do |item|
      reference_fields = item.keys & REFERENCE_PREFIXES.keys
      if allowed_fields.empty? && !reference_fields.empty?
        fail_with("#{file}: #{group} does not allow relationship fields: #{reference_fields.join(', ')}")
      end

      missing_fields = allowed_fields - reference_fields
      extra_fields = reference_fields - allowed_fields

      fail_with("#{file}: #{group} missing relationship fields: #{missing_fields.join(', ')}") unless missing_fields.empty?
      fail_with("#{file}: #{group} has disallowed relationship fields: #{extra_fields.join(', ')}") unless extra_fields.empty?
    end
  end
end

ids = []
refs = []

walk = lambda do |object|
  case object
  when Hash
    current_id = object["id"]
    ids << current_id if current_id

    if object.key?("associated_with")
      fail_with("associated_with is deprecated; use the allowed *_ids fields for this record type")
    end

    REFERENCE_PREFIXES.each do |field, prefix|
      next unless object.key?(field)

      values = object[field]
      if field.end_with?("_ids")
        fail_with("#{field} must be a list") unless values.is_a?(Array)
      else
        values = [values].compact
      end

      Array(values).each do |ref|
        ref = ref.to_s
        fail_with("Reference #{ref} does not match #{field} prefix #{prefix}") unless ref.start_with?(prefix)
        fail_with("Record #{current_id} should not reference itself") if current_id && ref == current_id
        refs << ref
      end
    end

    object.each_value { |value| walk.call(value) }
  when Array
    object.each { |value| walk.call(value) }
  end
end

data.each_value { |document| walk.call(document) }

duplicate_ids = ids.tally.select { |_id, count| count > 1 }
fail_with("Duplicate ids: #{duplicate_ids.keys.join(', ')}") unless duplicate_ids.empty?

bad_ids = ids.select { |id| id !~ /^[a-z]+(?:_[a-z]+)*_\d{2}$/ }
fail_with("Invalid id format: #{bad_ids.join(', ')}") unless bad_ids.empty?

missing_refs = refs.uniq - ids
fail_with("Unresolved refs: #{missing_refs.join(', ')}") unless missing_refs.empty?

DATE_CHECKS.each do |file, groups|
  document = data.fetch(file)
  groups.each do |group, field|
    values = Array(document[group]).filter_map { |item| item[field]&.to_s }
    next if values == values.sort

    fail_with("#{file}: #{group} is not sorted ascending by #{field}")
  end
end

puts "Data validation passed (#{FILES.length} YAML files, #{ids.length} ids)."
