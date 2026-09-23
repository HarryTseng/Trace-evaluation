#!/usr/bin/ruby
#
# Copyright Istio Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

require 'webrick'
require 'json'
require 'net/http'

# Otel
require 'opentelemetry/sdk'
require 'opentelemetry/exporter/otlp'

service_name = ENV['SERVICE_NAME'] || 'details'
service_version = ENV['SERVICE_VERSION'] || 'v1'
otlp_endpoint = ENV['OTEL_EXPORTER_OTLP_ENDPOINT'] || 'http://localhost:4318/v1/traces'

UPSTREAM_ERROR_RATE = (ENV['UPSTREAM_ERROR_RATE'] || '0.01').to_f
DOWNSTREAM_ERROR_RATE = (ENV['DOWNSTREAM_ERROR_RATE'] || '0.04').to_f

OpenTelemetry::SDK.configure do |c|
  c.service_name = service_name
  c.service_version = service_version
  
  c.use_all if respond_to?(:use_all)

  exporter = OpenTelemetry::Exporter::OTLP::Exporter.new(endpoint: otlp_endpoint)
  c.add_span_processor(
    OpenTelemetry::SDK::Trace::Export::BatchSpanProcessor.new(exporter)
  )
end

tracer = OpenTelemetry.tracer_provider.tracer('details-tracer')

if ARGV.length < 1 then
    puts "usage: #{$PROGRAM_NAME} port"
    exit(-1)
end

port = Integer(ARGV[0])

server = WEBrick::HTTPServer.new(
    :BindAddress => '*',
    :Port => port,
    :AcceptCallback => -> (s) { s.setsockopt(Socket::IPPROTO_TCP, Socket::TCP_NODELAY, 1) },
)

trap 'INT' do server.shutdown end

server.mount_proc '/health' do |req, res|
    res.status = 200
    res.body = {'status' => 'Details is healthy'}.to_json
    res['Content-Type'] = 'application/json'
end

server.mount_proc '/details' do |req, res|
begin
    #整理WEBrick header
    carrier = {}
    req.header.each do |k, v|
      carrier[k.downcase] = v.is_a?(Array) ? v.first.to_s : v.to_s
    end

    extracted_context = begin
      OpenTelemetry.propagation.extract(carrier)
    rescue => e
      OpenTelemetry.logger.error("Context extract failed: #{e.message}")
      OpenTelemetry::Context.current
    end
  
    OpenTelemetry::Context.with_current(extracted_context) do
      tracer.in_span('details') do |span|
        pathParts = req.path.split('/')
        headers = get_forward_headers(req)

        # Upstream error
        if rand < UPSTREAM_ERROR_RATE
          raise StandardError, "Upstream Error"
        end

        begin
          id = Integer(pathParts[-1])
          details = get_book_details(id, headers)

          # Downstream error
          if rand < (UPSTREAM_ERROR_RATE + DOWNSTREAM_ERROR_RATE)
            raise StandardError, "Downstream Error"
          end

          res.body = details.to_json
          res['Content-Type'] = 'application/json'
        rescue => error
          span.record_exception(error)
          span.status = OpenTelemetry::Trace::Status.error(error.message)
          res.body = {'error' => error.message}.to_json
          res['Content-Type'] = 'application/json'
          res.status = 400
        end
      end
    end
  rescue => outer_error
    puts "Outer Exception: #{outer_error.message}"
  end
end

# TODO: provide details on different books.
def get_book_details(id, headers)
    if ENV['ENABLE_EXTERNAL_BOOK_SERVICE'] === 'true' then
      # the ISBN of one of Comedy of Errors on the Amazon
      # that has Shakespeare as the single author
        isbn = '0486424618'
        return fetch_details_from_external_service(isbn, id, headers)
    end

    return {
        'id' => id,
        'author': 'William Shakespeare',
        'year': 1595,
        'type' => 'paperback',
        'pages' => 200,
        'publisher' => 'PublisherA',
        'language' => 'English',
        'ISBN-10' => '1234567890',
        'ISBN-13' => '123-1234567890'
    }
end

def fetch_details_from_external_service(isbn, id, headers)
    uri = URI.parse('https://www.googleapis.com/books/v1/volumes?q=isbn:' + isbn)
    http = Net::HTTP.new(uri.host, ENV['DO_NOT_ENCRYPT'] === 'true' ? 80:443)
    http.read_timeout = 5 # seconds

    # DO_NOT_ENCRYPT is used to configure the details service to use either
    # HTTP (true) or HTTPS (false, default) when calling the external service to
    # retrieve the book information.
    #
    # Unless this environment variable is set to true, the app will use TLS (HTTPS)
    # to access external services.
    unless ENV['DO_NOT_ENCRYPT'] === 'true' then
      http.use_ssl = true
    end

    request = Net::HTTP::Get.new(uri.request_uri)
    headers.each { |header, value| request[header] = value }

    response = http.request(request)

    json = JSON.parse(response.body)
    book = json['items'][0]['volumeInfo']

    language = book['language'] === 'en'? 'English' : 'unknown'
    type = book['printType'] === 'BOOK'? 'paperback' : 'unknown'
    isbn10 = get_isbn(book, 'ISBN_10')
    isbn13 = get_isbn(book, 'ISBN_13')

    return {
        'id' => id,
        'author': book['authors'][0],
        'year': book['publishedDate'],
        'type' => type,
        'pages' => book['pageCount'],
        'publisher' => book['publisher'],
        'language' => language,
        'ISBN-10' => isbn10,
        'ISBN-13' => isbn13
  }

end

def get_isbn(book, isbn_type)
  isbn_dentifiers = book['industryIdentifiers'].select do |identifier|
    identifier['type'] === isbn_type
  end

  return isbn_dentifiers[0]['identifier']
end

def get_forward_headers(request)
  headers = {}

  # Keep this in sync with the headers in productpage and reviews.
  incoming_headers = [
      # All applications should propagate x-request-id. This header is
      # included in access log statements and is used for consistent trace
      # sampling and log sampling decisions in Istio.
      'x-request-id',

      # Lightstep tracing header. Propagate this if you use lightstep tracing
      # in Istio (see
      # https://istio.io/latest/docs/tasks/observability/distributed-tracing/lightstep/)
      # Note: this should probably be changed to use B3 or W3C TRACE_CONTEXT.
      # Lightstep recommends using B3 or TRACE_CONTEXT and most application
      # libraries from lightstep do not support x-ot-span-context.
      'x-ot-span-context',

      # Datadog tracing header. Propagate these headers if you use Datadog
      # tracing.
      'x-datadog-trace-id',
      'x-datadog-parent-id',
      'x-datadog-sampling-priority',

      # W3C Trace Context. Compatible with OpenCensusAgent and Stackdriver Istio
      # configurations.
      'traceparent',
      'tracestate',

      # Cloud trace context. Compatible with OpenCensusAgent and Stackdriver Istio
      # configurations.
      'x-cloud-trace-context',

      # Grpc binary trace context. Compatible with OpenCensusAgent nad
      # Stackdriver Istio configurations.
      'grpc-trace-bin',

      # b3 trace headers. Compatible with Zipkin, OpenCensusAgent, and
      # Stackdriver Istio configurations.
      'x-b3-traceid',
      'x-b3-spanid',
      'x-b3-parentspanid',
      'x-b3-sampled',
      'x-b3-flags',

      # SkyWalking trace headers.
      'sw8',

      # Application-specific headers to forward.
      'end-user',
      'user-agent',

      # Context and session specific headers
      'cookie',
      'authorization',
      'jwt'
  ]

  request.each do |header, value|
    if incoming_headers.include? header then
      headers[header] = value
    end
  end

  return headers
end

server.start
