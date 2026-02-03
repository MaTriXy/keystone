#!/usr/bin/env perl
use strict;
use warnings;
use Test::More;
use File::Temp qw(tempfile);
use IPC::Open3;
use Symbol 'gensym';

my $script = "$FindBin::Bin/timestamp_process_output.pl";

BEGIN { use FindBin; }
$script = "$FindBin::Bin/timestamp_process_output.pl";

# Helper to run the script and capture output
sub run_script {
    my @args = @_;
    my $err = gensym;
    my $pid = open3(my $in, my $out, $err, $script, @args);
    close $in;
    my @stdout = <$out>;
    my @stderr = <$err>;
    waitpid($pid, 0);
    my $exit_code = $? >> 8;
    return (\@stdout, \@stderr, $exit_code);
}

# Test 1: Basic stdout capture
subtest 'captures stdout with correct format' => sub {
    my ($out, $err, $code) = run_script('echo', 'hello world');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 1, 'one line of output');
    like($out->[0], qr/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\tSTDOUT\thello world\n$/, 
         'output matches expected format');
};

# Test 2: Basic stderr capture
subtest 'captures stderr with correct format' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'echo error >&2');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 1, 'one line of output');
    like($out->[0], qr/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\tSTDERR\terror\n$/, 
         'stderr matches expected format');
};

# Test 3: Mixed stdout and stderr
subtest 'captures both stdout and stderr' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'echo out; echo err >&2');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 2, 'two lines of output');
    my $has_stdout = grep { /\tSTDOUT\tout\n$/ } @$out;
    my $has_stderr = grep { /\tSTDERR\terr\n$/ } @$out;
    ok($has_stdout, 'stdout line present');
    ok($has_stderr, 'stderr line present');
};

# Test 4: Preserves exit code
subtest 'preserves child exit code' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'exit 42');
    is($code, 42, 'exit code preserved');
};

# Test 5: Logfile option
subtest 'writes to logfile when specified' => sub {
    my ($fh, $logfile) = tempfile(UNLINK => 1);
    close $fh;
    
    my ($out, $err, $code) = run_script('--logfile', $logfile, 'echo', 'logged');
    is($code, 0, 'exit code is 0');
    
    open my $log, '<', $logfile or die "Cannot open $logfile: $!";
    my @lines = <$log>;
    close $log;
    
    is(scalar @lines, 1, 'one line in logfile');
    like($lines[0], qr/\tSTDOUT\tlogged\n$/, 'logfile contains correct format');
};

# Test 6: Multiple lines
subtest 'handles multiple lines' => sub {
    my ($out, $err, $code) = run_script('bash', '-c', 'echo one; echo two; echo three');
    is($code, 0, 'exit code is 0');
    is(scalar @$out, 3, 'three lines of output');
    for my $line (@$out) {
        like($line, qr/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\tSTDOUT\t/, 
             'each line has correct prefix');
    }
};

# Test 7: No command shows usage
subtest 'shows usage without command' => sub {
    my ($out, $err, $code) = run_script();
    isnt($code, 0, 'non-zero exit code');
    like($err->[0], qr/Usage:/, 'shows usage message');
};

# Test 8: Tab-separated format is parseable
subtest 'output is tab-separated and parseable' => sub {
    my ($out, $err, $code) = run_script('echo', 'test message');
    my @fields = split /\t/, $out->[0];
    is(scalar @fields, 3, 'three tab-separated fields');
    like($fields[0], qr/^\d{4}-\d{2}-\d{2}T/, 'first field is timestamp');
    is($fields[1], 'STDOUT', 'second field is stream type');
    like($fields[2], qr/^test message\n$/, 'third field is message');
};

done_testing();
